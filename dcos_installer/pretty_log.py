import coloredlogs

coloredlogs.install(
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
            'color': 'blue'
        }
    },
    fmt='%(asctime)s :: %(message)s'
)
