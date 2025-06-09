from collections import namedtuple

fields = [
    'RATING',
    'COMMENT',
    'SURVEY_MEETING_FORMAT',
    'SURVEY_MEETING_TOPICS',
    'SURVEY_MEETING_FREQUENCY',
    'SURVEY_MEETING_HELPS',
    'SURVEY_MEETING_END',
    'FINISH',
]
bot_States = namedtuple('bot_States', fields)
STATES = bot_States(*range(len(fields)))


_survey_fields = [
        'meeting_format',
        'meeting_topics',
        'meeting_frequency',
        'meeting_help',
    ]

survey_keys = namedtuple(
    'survey_keys',
    _survey_fields
)
SURVEY_KEYS = survey_keys(*_survey_fields)