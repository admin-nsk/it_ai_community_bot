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

SURVEY_KEYS = namedtuple(
    'survey_keys',
    [
        'meeting_format',
        'meeting_topics',
        'meeting_frequency',
        'meeting_help',
    ]
)