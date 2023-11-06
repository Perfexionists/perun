def parse_strategy(strategy):
    """..."""
    short_strings = {
        "aat": "average_amount_threshold",
        "bmoe": "best_model_order_equality",
    }
    if strategy in short_strings.keys():
        return short_strings[strategy]
    else:
        return strategy
