import re
from typing import TYPE_CHECKING, Optional, Generator

import pandas as pd
import numpy as np

from perun.utils.structs import DegradationInfo
import perun.check.factory as check
import perun.profile.convert as convert

if TYPE_CHECKING:
    from perun.profile.factory import Profile

__author__ = 'Jiri Pavela'


MZS_CORRECTION = 0.6745


class DiffProfile:
    def __init__(self, baseline_profile: Profile, target_profile: Profile, location_filter: Optional[str]) -> None:
        self.location_filter: Optional[str] = location_filter
        self.df: pd.DataFrame = self._merge_and_diff(
            self._prepare_profile(baseline_profile), self._prepare_profile(target_profile)
        )

    def detect_changes(self) -> Generator[DegradationInfo, None, None]:
        pass

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
        stddev = df_filtered['total exc. T Δ [ms]'].std()
        self.df['StdDev multiple'] = self.df['total exc. T Δ [ms]'] / stddev
        stddev_filter = (self.df['StdDev multiple'] < -1.0) | (self.df['StdDev multiple'] > 1.0)
        self.df['StdDev flag'] = stddev_filter

    def new_deleted_functions(self) -> None:
        new_removed_filter = (
                self.df['+total exc. T [ms]'].isna() | self.df['-total exc. T [ms]'].isna()
        )
        self.df['NewDel flag'] = new_removed_filter

    def _prepare_profile(self, profile: Profile) -> pd.DataFrame:
        columns = ['uid', 'exclusive', 'loc']
        # Obtain "Uid (function name), exclusive time, location" DataFrame
        # and sum the exclusive times of individual functions
        df = convert.resources_to_pandas_dataframe(profile)[columns]\
            .groupby(['uid', 'loc']).sum().reset_index()
        # Filter the location based on the provided regex filter
        if self.location_filter is not None:
            return df[df['loc'].str.contains(self.location_filter, regex=True, na=False)]
        return df

    @staticmethod
    def _merge_and_diff(baseline_profile: pd.DataFrame, target_profile: pd.DataFrame) -> pd.DataFrame:
        # Rename the exclusive time columns appropriately (- for old, + for new) and merge them
        baseline_profile.rename(columns={'exclusive': '-exclusive T [ms]'})
        target_profile.rename(columns={'exclusive': '+exclusive T [ms]'})
        df_merge = pd.merge(target_profile, baseline_profile, on='name', how='left')
        # Compute the exclusive time diff
        df_merge['exclusive T Δ [ms]'] = df_merge.apply(
            lambda row: row['+exclusive T [ms]'] - row['-exclusive T [ms]']
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


def exclusive_time_outliers(baseline_profile: Profile, target_profile: Profile, location_filter: Optional[str], **_):
    diff_prof = DiffProfile(baseline_profile, target_profile, location_filter)


