import coloredlogs

coloredlogs.install(
    level='DEBUG',
    datefmt='%H:%M:%S',
    level_styles={
        'info': {
            'color': 'blue'
        },
        'debug': {
            'color': 'cyan'
        },
        'warn': {
            'color': 'yellow'
        },
        'error': {
            'color': 'red',
            'bold': True,
        },
    },
    field_styles={
        'levelname': {
            'color': 'white',
            'bold': True
        },
        'asctime': {
            'color': 'magenta'
        },
        'name': {
            'color': 'white'
        }
    },
    fmt='%(asctime)s :: %(name)s :: %(levelname)s :: %(message)s'
)
