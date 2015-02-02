# AuroraWatch API v1.0 (draft)

This is the proposed API v1.0 for AuroraWatch UK. It is subject to
change.

## current_status.xml

The current activity status and activity value for the present
hour. If just past the hour and an activity status is not available
for the current hour this should contain the status and timestamp for
the previous hour. This may also include a status message (along with
time of issue and time-to-live for the message). The status message
can contain an optional URL.

Does not include the sites to attribute. Fetch `activity.xml` to
obtain the list of `site_ids` from the `recent_activity` element. Be
aware that `activity.xml` could be more recent and so the final value
could apply to a later hour.

## activity.xml

Activity values for the last 24 hours. Each activity value also
contains the maximum status level reached during the hour. May also
contain a status message as described above.

## projects.xml

A list of `project`s and `site`s associated with the AuroraWatch
notifications. Not all sites may be used for notifications; see the
`site_ids` attribute of the `recent_activity` element in
`activity.xml` to determine which projects and sites are currently
being used.

## status_list.xml

The list of status levels, their `meaning` and a short `description`. Also
included for each level is the `lower_threshold` and standard RGB `color`
value used by AuroraWatch UK. For consistency please use the same
colors.
