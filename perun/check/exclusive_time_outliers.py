from typing import Optional, Generator, Dict, List, Tuple
from difflib import SequenceMatcher, get_close_matches

import pandas as pd
import numpy as np

from perun.utils.structs import DegradationInfo
from perun.check.factory import PerformanceChange
import perun.profile.convert as convert

from perun.profile.factory import Profile

__author__ = 'Jiri Pavela'


MZS_CORRECTION = 0.6745


def exclusive_time_outliers(baseline_profile: Profile, target_profile: Profile, location_filter: Optional[str] = None, **_):
    diff_prof = DiffProfile(baseline_profile, target_profile, location_filter)
    yield from diff_prof.detect_changes()


class DiffProfile:
    def __init__(self, baseline_profile: Profile, target_profile: Profile, location_filter: Optional[str] = None) -> None:
        self.location_filter: Optional[str] = location_filter
        self.df: pd.DataFrame = self._merge_and_diff(
            self._prepare_profile(baseline_profile), self._prepare_profile(target_profile)
        )

    def detect_changes(self) -> Generator[DegradationInfo, None, None]:
        # Run three outlier detection methods, where z-score flags the most significant outliers
        # and StdDev flags the least significant ones
        self.modified_z_score()
        self.iqr_multiple()
        self.std_dev_multiple()
        self.new_deleted_functions()

        # Transform the DataFrame to DegradationInfo for each function in the DF
        for _, row in self.df.iterrows():
            result, ct, cr = self._determine_result_and_confidence(row)
            yield DegradationInfo(
                res=result,
                loc=row['uid'],
                fb=str(row['-exclusive T [ms]']),
                tt=str(row['+exclusive T [ms]']),
                t='exclusive time',
                rd=row['exclusive T Δ [ms]'],
                # row['prog exclusive T Δ [%]'],  First add the relative rate
                ct=ct,
                cr=cr
            )

        # Provide a summary degradation / optimization info per location (binary)
        columns = [
            'location',
            '-exclusive T [ms]', '+exclusive T [ms]',
            'exclusive T Δ [ms]', 'prog exclusive T Δ [%]'
        ]
        for _, row in self.df[columns].groupby(['location']).sum().reset_index().iterrows():
            yield DegradationInfo(
                res=PerformanceChange.TotalDegradation if row['prog exclusive T Δ [%]'] > 0 else PerformanceChange.TotalOptimization,
                loc=row['location'],
                fb=self.df['-exclusive T [ms]'],
                tt=self.df['+exclusive T [ms]'],
                t='exclusive time',
                rd=self.df['exclusive T Δ [ms]'],
                # self.df['prog exc. T Δ [%]'].sum(),  Relative rate
                ct='N/A'
            )

    @staticmethod
    def _determine_result_and_confidence(row: pd.Series) -> Tuple[PerformanceChange, str, float]:
        exc_time = row['exclusive T Δ [ms]']
        if row['Mzs flag']:
            result = PerformanceChange.SevereDegradation if exc_time > 0 else PerformanceChange.SevereOptimization
            # We use IQR multiple instead of the mod. z-score to make the human comparison easier
            # ct, cr = 'Modified Z-score', row['Modified Z-score']
            ct, cr = 'IQR multiple', row['IQR multiple']
        elif row['IQR flag']:
            result = PerformanceChange.Degradation if exc_time > 0 else PerformanceChange.Optimization
            ct, cr = 'IQR multiple', row['IQR multiple']
        elif row['StdDev flag']:
            result = PerformanceChange.MaybeDegradation if exc_time > 0 else PerformanceChange.MaybeOptimization
            ct, cr = 'StdDev multiple', row['StdDev multiple']
        else:
            result = PerformanceChange.NoChange
            ct, cr = 'StdDev multiple', row['StdDev multiple']

        # Update the result if the function is actually new or deleted
        if row['NewDel flag']:
            result = PerformanceChange.NotInBaseline if exc_time > 0 else PerformanceChange.NotInTarget

        return result, ct, cr

    def modified_z_score(self) -> None:
        # https://www.kaggle.com/code/jainyk/anomaly-detection-using-zscore-and-modified-zscore/notebook
        # https://medium.com/analytics-vidhya/anomaly-detection-by-modified-z-score-f8ad6be62bac
        #   - General introduction
        # https://hwbdocuments.env.nm.gov/Los%20Alamos%20National%20Labs/TA%2054/11587.pdf
        #   - Recommendation for cut-off score 3.5
        #
        # Modified z-score yi = (xi − X_median) / (k * MAD)
        #   - MAD is the median of the absolute deviation from the median.
        #   - k is a consistency correction
        mad = self.df['exclusive T Δ [ms]'].mad()
        median = self.df['exclusive T Δ [ms]'].median()
        self.df['AD'] = abs(self.df['exclusive T Δ [ms]'] - median)
        try:
            self.df['Modified Z-score'] = (MZS_CORRECTION * self.df[['AD']]) / mad
        except ZeroDivisionError:
            mad = np.nextafter(0, 1)
            self.df['Modified Z-score'] = (MZS_CORRECTION * self.df[['AD']]) / mad
        mzs_filter = (self.df['Modified Z-score'] < -3.5) | (self.df['Modified Z-score'] > 3.5)
        # Flag for easier filtering
        self.df['Mzs flag'] = mzs_filter

    def iqr_multiple(self) -> None:
        # Compute IQR
        q1 = self.df['exclusive T Δ [ms]'].quantile(0.25)
        q3 = self.df['exclusive T Δ [ms]'].quantile(0.75)
        iqr = q3 - q1
        # Create an IQR filter based on the distance of 1.5 * IQR from Q1 and Q3
        below_low_base = self.df['exclusive T Δ [ms]'] < q1 - 1.5 * iqr
        above_up_base = self.df['exclusive T Δ [ms]'] > q3 + 1.5 * iqr
        iqr_filter = (below_low_base | above_up_base)
        # Compute the IQR multiple for outliers
        self.df.loc[below_low_base, 'IQR multiple'] = -((self.df['exclusive T Δ [ms]'] - q1) / iqr)
        self.df.loc[above_up_base, 'IQR multiple'] = self.df['exclusive T Δ [ms]'] / iqr - q3
        # Flag for easier filtering
        self.df['IQR flag'] = iqr_filter

    def std_dev_multiple(self) -> None:
        df_filtered = self.df.loc[~(self.df['Mzs flag']) & ~(self.df['IQR flag'])]
        stddev = df_filtered['exclusive T Δ [ms]'].std()
        self.df['StdDev multiple'] = self.df['exclusive T Δ [ms]'] / stddev
        stddev_filter = (self.df['StdDev multiple'] < -2.0) | (self.df['StdDev multiple'] > 2.0)
        self.df['StdDev flag'] = stddev_filter

    def new_deleted_functions(self) -> None:
        new_removed_filter = (
                self.df['+exclusive T [ms]'].isna() | self.df['-exclusive T [ms]'].isna()
        )
        self.df['NewDel flag'] = new_removed_filter

    def _prepare_profile(self, profile: Profile) -> pd.DataFrame:
        columns = ['uid', 'exclusive', 'location']
        # Obtain "Uid (function name), exclusive time, location" DataFrame
        # and sum the exclusive times of individual functions
        df = convert.resources_to_pandas_dataframe(profile)[columns]\
            .groupby(['uid', 'location']).sum().reset_index()
        # Filter the location based on the provided regex filter
        if self.location_filter is not None:
            return df[df['location'].str.contains(self.location_filter, regex=True, na=False)]
        return df

    @staticmethod
    def _merge_and_diff(baseline_profile: pd.DataFrame, target_profile: pd.DataFrame) -> pd.DataFrame:
        # Rename the exclusive time columns appropriately (- for old, + for new) and merge them
        baseline_profile.rename(columns={'exclusive': '-exclusive T [ms]'}, inplace=True)
        target_profile.rename(columns={'exclusive': '+exclusive T [ms]'}, inplace=True)
        # Rename the locations in the baseline and target profiles to match. We employ a string
        # similarity check to discover possible changes of binaries name, e.g., due to version num.
        rename_old, rename_new = _map_similar_names(
            list(baseline_profile['location'].unique()), list(target_profile['location'].unique())
        )
        baseline_profile['location'].replace(rename_old, inplace=True)
        target_profile['location'].replace(rename_new, inplace=True)

        df_merge = pd.merge(target_profile, baseline_profile, on=['uid', 'location'], how='left')
        # Compute the exclusive time diff
        df_merge['exclusive T Δ [ms]'] = df_merge.apply(
            lambda row: row['+exclusive T [ms]'] - row['-exclusive T [ms]'], axis=1
        )
        # Prepare filters
        new_nan_filt = df_merge['+exclusive T [ms]'].isna()
        old_nan_filt = df_merge['-exclusive T [ms]'].isna()
        no_nan_filt = ~(df_merge['-exclusive T [ms]'].isna() | df_merge['-exclusive T [ms]'].isna())
        # Compute the sum of all exclusive times
        total_exc = df_merge['+exclusive T [ms]'].sum()
        # Compute the impact of change on the total program exclusive time
        df_merge.loc[new_nan_filt, 'prog exclusive T Δ [%]'] = (
                df_merge['-exclusive T [ms]'] / total_exc * (-100)
        )
        df_merge.loc[old_nan_filt, 'prog exclusive T Δ [%]'] = (
                df_merge['+exclusive T [ms]'] / total_exc * 100
        )
        df_merge.loc[no_nan_filt, 'prog exclusive T Δ [%]'] = (
                (df_merge['+exclusive T [ms]'] - df_merge['-exclusive T [ms]']) / total_exc * 100
        )
        # Sort by the most significant time difference
        return df_merge.sort_values(by='exclusive T Δ [ms]', ascending=False).reset_index(drop=True)


def _map_similar_names(strings_old: List[str], strings_new: List[str]) -> Tuple[Dict[str, str], Dict[str, str]]:
    renames_old, renames_new = {}, {}
    for old_name in strings_old:
        matching_name = get_close_matches(old_name, strings_new, n=1)
        # If no match was found, no rename will be done
        if matching_name:
            # We found a match and now we want to find the longest common prefix
            match = matching_name[0]
            lcp = SequenceMatcher(None, old_name, match).find_longest_match(
                0, len(old_name), 0, len(match)
            )
            new_name = str(match[lcp.b:lcp.b + lcp.size]) + "_"
            # Update the rename map
            renames_old[old_name] = new_name
            renames_new[str(match)] = new_name
            # Remove the already matched name
            strings_new.remove(str(match))
    return renames_old, renames_new

