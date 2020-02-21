import itertools

__author__ = 'Tomas Fiedor'


def profile_filter(generator, rule, return_type='prof'):
    """Finds concrete profile by the rule in profile generator.

    Arguments:
        generator(generator): stream of profiles as tuple: (name, dict)
        rule(str): string to search in the name

    Returns:
        Profile: first profile with name containing the rule
    """
    generator, teed_generator = itertools.tee(generator, 2)
    # Loop the generator and test the rule
    for profile in teed_generator:
        if rule in profile[0]:
            if return_type == 'prof':
                return profile[1]
            elif return_type == 'name':
                return profile[0]
            else:
                return profile

