HARDWARE_SCHEMA = {
    'type': {
        'type': str,
        'required': True,
    },
    'discovery': {
        'type': str,
        'required': False
    },
    'setup': {
        'type': list,
        'required': False,
        'elements': {
            'topic': {
                'type': str,
                'required': True
            },
            'store': {
                'type': str,
                'required': True
            }
        }
    },
    'instance_id': {
        'type': str,
        'required': True
    },
    'device_info': {
        'type': dict,
        'required': True,
        'elements': {

        },
    },
    'entities': {
        'type': list,
        'elements': {
            'name': {
                'type': str,
                'required': False,
            },
            'entity_id': {
                'type': str,
                'required': True,
            },
            'topic': {
                'type': str,
                'required': True
            },
            'device_class': {
                'type': str,
                'required': False
            },
            'unit_of_measurement': {
                'type': str,
                'required': False
            },
            'icon': {
                'type': str,
                'required': False
            },
            'value_template': {
                'type': str,
                'required': False
            },
            'component': {
                'type': str,
                'required': False
            }
        }
    }
}