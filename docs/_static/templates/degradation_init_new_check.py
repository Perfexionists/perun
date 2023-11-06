def parse_strategy(strategy):
    """..."""
    short_strings = {
        "aat": "average_amount_threshold",
        "bmoe": "best_model_order_equality",
        "mdc": "my_degradation_checker",
    }
    if strategy in short_strings.keys():
        return short_strings[strategy]
    else:
        return strategy
