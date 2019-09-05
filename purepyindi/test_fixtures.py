import datetime
from .constants import (
    INDIActions,
    INDIPropertyKind,
    PropertyPerm,
    PropertyState,
)

DEF_NUMBER_PROP = b'''
<defNumberVector device="test" name="prop" state="Idle" perm="rw" timestamp="2019-08-12T20:49:50.420459Z">
	<defNumber name="value" format="%g" min="0" max="0" step="0">
0
	</defNumber>
</defNumberVector>
'''
DEF_NUMBER_UPDATE = {
    'action': INDIActions.PROPERTY_DEF,
    'device': 'test',
    'property': {
        'name': 'prop',
        'kind': INDIPropertyKind.NUMBER,
        'elements': {
            'value': {
                'format': '%g',
                'max': 0.0,
                'min': 0.0,
                'name': 'value',
                'step': 0.0,
                'value': 0.0
            },
        },
        'perm': PropertyPerm.READ_WRITE,
        'state': PropertyState.IDLE,
        'timestamp': datetime.datetime(2019, 8, 12, 20, 49, 50, 420459, tzinfo=datetime.timezone.utc)
    }
}

SET_NUMBER_PROP = b'''
<setNumberVector device="test" name="prop" state="Idle" timestamp="2019-08-12T20:49:50.420459Z">
	<oneNumber name="value">
1
	</oneNumber>
</setNumberVector>
'''

SET_NUMBER_UPDATE = {
    'action': INDIActions.PROPERTY_SET,
    'device': 'test',
    'property': {
        'name': 'prop',
        'kind': INDIPropertyKind.NUMBER,
        'elements': {
            'value': {'name': 'value', 'value': 1.0}
        },
        'state': PropertyState.IDLE,
        'timestamp': datetime.datetime(2019, 8, 12, 20, 49, 50, 420459, tzinfo=datetime.timezone.utc)
    }
}

NEW_NUMBER_MUTATION = {
    'action': INDIActions.PROPERTY_NEW,
    'device': 'test',
    'property': {
        'name': 'prop',
        'kind': INDIPropertyKind.NUMBER,
        'elements': {
            'value': {
                'format': '%g',
                'max': 0.0,
                'min': 0.0,
                'name': 'value',
                'step': 0.0,
                'value': 0.0
            }
        },
    },
}

NEW_NUMBER_TIMESTAMP = datetime.datetime(2019, 8, 13, 22, 45, 17, 867692, tzinfo=datetime.timezone.utc)

NEW_NUMBER_MESSAGE = b'''<newNumberVector device="test" name="prop" timestamp="2019-08-13T22:45:17.867692Z"><oneNumber name="value">0</oneNumber></newNumberVector>\n'''

DEL_PROPERTY_MESSAGE = b'''<delProperty device="test" timestamp="2019-09-03T21:45:04.031508Z">\r\n</delProperty>'''

DEL_PROPERTY_UPDATE = {
    'action': INDIActions.PROPERTY_DEL,
    'device': 'test',
    'timestamp': datetime.datetime(2019, 9, 3, 21, 45, 4, 31508, tzinfo=datetime.timezone.utc),
}
