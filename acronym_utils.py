from typing import List

import discord
from aiohttp import ClientSession

DECRONYM = "http://decronym.xyz/acronyms/Space.json"


async def acronym_lookup(session: ClientSession, acronym: str) -> List[str]:
    async with session.get(DECRONYM) as response:
        if response.status == 200:
            decronyms = await response.json()
        else:
            return []

    if acronym.upper() in decronyms:
        return decronyms[acronym.upper()]
    else:
        return []

def get_acronym_embed(acronym: str, definitions: List[str]):
    embed = discord.Embed()
    embed.title = acronym.upper()
    if len(definitions) == 1:
        def_message = definitions[0]
    else:
        def_message = ""
        for i, definition in enumerate(definitions, start=1):
            def_message += "{}. {}\n".format(i, definition)
    embed.description = def_message.strip()
    embed.set_footer(text="Data from decronym.xyz")
    return embed