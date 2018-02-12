# Discord Launch Alerts

Rocket launch lookup and alerts bot.

Uses the rocketlaunch.live API to serve information.

Commands

- !launch next [num] ["string filter"]
- !launch today
- !launch config [option] [value]
    - receive_alerts: Takes a boolean (True/False) as a value
    - alert_times: Takes a comma delimited list of time to launch times for when alerts will be sent out.
        - Example: "24h, 12h, 10h54m, 15m"
    - timezone - Takes a Timezone Abbreviation as a value
