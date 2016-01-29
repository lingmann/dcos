import coloredlogs


def colored_log(level):
    coloredlogs.install(
        level=level,
        datefmt='%H:%M:%S',
        level_styles={
            'warn': {
                'color': 'yellow'
            },
            'error': {
                'color': 'red',
                'bold': True,
            },
        },
        field_styles={
            'asctime': {
                'color': 'magenta'
            },
            'name': {
                'color': 'magenta',
                'bold': True
            }
        },
        fmt='%(asctime)s %(message)s',
        isatty=True

    )
