from json import loads, dumps
import discord
import redis


class ConfigItem:
    def __init__(self, name, default, help_text):
        self.name = name
        self.default = default
        self.help_text = help_text
        self.value = self.default

    def get_key_value(self):
        return {self.name: self.value}


class Config:
    def __init__(self):
        self._config_items = self._get_config_items()
        self.db = redis.StrictRedis(host='localhost')  # TODO: Make DB configurable in local_config
        self._get_config_from_db()

    def _get_config_from_db(self):
        key_name = self._get_db_key_name()
        db_data = self.db.get(key_name)
        if db_data:
            config_in_db = loads(db_data)
            for config_item in self._config_items:
                if config_item.name in config_in_db:
                    config_item.value = config_in_db[config_item.name]

    def _set_config_on_db(self):
        config_items_list = {}
        for config_item in self._config_items:
            if config_item.value != config_item.default:
                config_items_list[config_item.name] = config_item.value

        key_name = self._get_db_key_name()
        self.db.set(key_name, dumps(config_items_list))

    def _get_db_key_name(self):
        raise NotImplementedError

    def _get_config_items(self):
        raise NotImplementedError

    def _get_config_item_from_str(self, item):
        if "_config_items" in self.__dict__:
            for config_item in self._config_items:
                if config_item.name == item.lower():
                    return config_item

        return None

    def __getattr__(self, item):
        config_item = self._get_config_item_from_str(item)
        if config_item is not None:
            return config_item.value
        raise AttributeError

    def __setattr__(self, item, value):
        config_item = self._get_config_item_from_str(item)
        if config_item is None:
            self.__dict__[item] = value
            return

        config_item.value = value
        self._set_config_on_db()

    def config_options_embed(self):
        embed = discord.Embed()
        embed.title = "Launch Alerts Options"
        embed.description = "Launch Alerts supports the following configuration options.\n" \
                            "Set using `!launch config [option] [value]`."
        for config_item in self._config_items:
            embed_value = "Default: {}\nCurrently: {}\n{}".format(config_item.default,
                                                                  self.__getattr__(config_item.name),
                                                                  config_item.help_text)
            embed.add_field(name=config_item.name, value=embed_value, inline=True)

        return embed


class ChannelConfig(Config):
    KEY_PREFIX = 'config-channel'

    def __init__(self, server_id: str, channel_id: str):
        self.server_id = server_id
        self.channel_id = channel_id
        super().__init__()

    def _get_db_key_name(self):
        return '{}-{}-{}'.format(self.KEY_PREFIX, self.server_id, self.channel_id)

    def _get_config_items(self):
        return [
            ConfigItem("receive_alerts", "false", "Receive alerts for upcoming launches in this channel"),
            ConfigItem("alert_times", "24h, 12h, 6h, 3h, 1h, 15m", "Comma separated list of time to launch for alerts"),
            ConfigItem("timezone", "UTC", "Timezone for messages in this channel"),
        ]


class UserConfig(Config):
    KEY_PREFIX = 'config-user'

    def __init__(self, user_id):
        self.user_id = user_id
        super().__init__()

    def _get_db_key_name(self):
        return '{}-{}'.format(self.KEY_PREFIX, self.user_id)

    def _get_config_items(self):
        return [
            ConfigItem("receive_alerts", "false", "Receive alerts for upcoming launches"),
            ConfigItem("alert_times", "24h, 12h, 6h, 3h, 1h, 15m", "Comma separated list of time to launch for alerts"),
            ConfigItem("timezone", "UTC", "Timezone for messages"),
        ]
