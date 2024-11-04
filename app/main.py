import os
import discord
import datetime
import time
import re
from discord.ext import tasks
import asyncio
import aiohttp
from server import server_thread
import dotenv

dotenv.load_dotenv()

TOKEN = os.environ.get('TOKEN')

intents = discord.Intents.default()
intents.message_content = True

client = discord.Bot(intents=intents) 
guild_id = 0 # your server id

sent_world_ids = set()


@client.event
async def on_ready():
  guild = client.get_guild(guild_id)
  channel = get_channel_by_name(guild, 'bot-dev')
  if channel is not None:
    await channel.send('deployed successfully or bot restarted!')


# - Main -
async def send_nicknames_periodically():
    await client.wait_until_ready()

    guild = client.get_guild(guild_id)

    global sent_world_ids

    while not client.is_closed():
        try:
            data = await fetch_data()

            current_world_ids = {entry['worldId'] for entry in data if 'worldId' in entry}

            sent_world_ids = {world_id: sent_world_ids[world_id] for world_id in sent_world_ids if world_id in current_world_ids}

            for entry in data:
                # get world data
                world_id = entry['worldId']
                event_list = entry.get('eventList', [])

                if event_list:
                    max_event = max(event_list, key=lambda event: event.get('igt', -1))
                    max_igt = max_event.get('igt', -1)
                    event_id = max_event.get('eventId', None)

                    if world_id not in sent_world_ids or max_igt > sent_world_ids[world_id][1]:
                        # get basic data
                        game_version = entry.get('gameVersion', None)
                        if game_version != '1.16.1':
                            continue
                        nickname = entry['nickname']
                        live_account = entry.get('user', {}).get('liveAccount', None)
                        item_data = entry.get('itemData', {}).get('estimatedCounts', {})
                        ender_pearl_count = item_data.get('minecraft:ender_pearl', None)
                        blaze_rod_count = item_data.get('minecraft:blaze_rod', None)

                        events_info = f'eventId: {event_id}, igt: {max_igt}'

                        # get all pace
                        list_pace = await get_all_pace()
                        if list_pace == -1:
                            # log
                            print('not exist pacemanbot-runner-pbpaces channel')

                        found = False
                        for i in range(0, len(list_pace), 7):
                            if list_pace[i] in nickname:
                                # add :00
                                for m in range(1, 7):
                                    if list_pace[i + m].find(':') == -1:
                                        list_pace[i + m] = f'{list_pace[i + m]}:00'
                                found = True
                                break

                        # continue if user not found
                        if not found:
                            continue

                        # continue if not in events
                        if event_id not in {'rsg.enter_bastion', 'rsg.enter_fortress', 'rsg.first_portal', 'rsg.enter_stronghold', 'rsg.enter_end', 'rsg.credits'}:
                            continue

                        # log
                        print(list_pace)
                        print(
                            f'worldId: {world_id}\n'
                            f'nickname: {nickname}\n'
                            f'gameVersion: {game_version}\n'
                            f'liveAccount: {live_account}\n'
                            f'ender_pearl: {ender_pearl_count}, blaze_rod: {blaze_rod_count}\n'
                            f'{events_info}'
                        )
                        print(f'find name, pb pace and pb: {list_pace[i]}/{list_pace[i+1]}/{list_pace[i+2]}/{list_pace[i+3]}/{list_pace[i+4]}/{list_pace[i+5]}/{list_pace[i+6]}') # name/fs/ss/b/e/ee/pb
                        
                        # set data
                        dt_now = datetime.datetime.now()
                        time = convert_to_hh_mm_ss(max_igt)
                        ss_time = list_pace[i + 2]
                        b_time = list_pace[i + 3]
                        e_time = list_pace[i + 4]
                        ee_time = list_pace[i + 5]
                        pb_time = list_pace[i + 6]
                        pbtitle= ''
                        pbdif = ''
                        item = ''
                        role = None

                        # get role and misc
                        if event_id == 'rsg.enter_bastion' or event_id == 'rsg.enter_fortress':
                            if world_id in sent_world_ids:
                                if sent_world_ids[world_id][0] == 'rsg.enter_bastion' or sent_world_ids[world_id][0] == 'rsg.enter_fortress':
                                    if time_to_seconds(ss_time) > time_to_seconds(time):
                                        role = discord.utils.get(guild.roles, name='*SSPB')
                                    else:
                                        role = discord.utils.get(guild.roles, name='*SS')
                                else:
                                    role = discord.utils.get(guild.roles, name='*FS')
                            else:
                                role = discord.utils.get(guild.roles, name='*FS')

                        elif event_id == 'rsg.first_portal':
                            if time_to_seconds(b_time) > time_to_seconds(time):
                                role = discord.utils.get(guild.roles, name='*BPB')
                            else:
                                role = discord.utils.get(guild.roles, name='*B')

                        elif event_id == 'rsg.enter_stronghold':
                            if time_to_seconds(e_time) > time_to_seconds(time):
                                role = discord.utils.get(guild.roles, name='*EPB')
                            else:
                                role = discord.utils.get(guild.roles, name='*E')

                        elif event_id == 'rsg.enter_end':
                            if time_to_seconds(ee_time) > time_to_seconds(time):     
                                dif = string_to_datetime(list_pace[i+6]) - string_to_datetime(time)
                                pbdif = f'  (Exceed the PB in {convert_to_unix_time(dt_now, dif)})'
                                role = discord.utils.get(guild.roles, name='*EEPB')
                            else:
                                role = discord.utils.get(guild.roles, name='*EE')
                          
                        elif event_id == 'rsg.credits':
                            if time_to_seconds(pb_time) > time_to_seconds(time):
                                pbtitle = ' New PB!!    '
                                dif = string_to_datetime(list_pace[i+6]) - string_to_datetime(time)
                                pbdif = f'  (-{str(dif)[2:]})'
                                role = discord.utils.get(guild.roles, name='*NPB')
                            elif time_to_seconds(pb_time) == time_to_seconds(time):
                                pbtitle = ' New PB??    '   
                                dif = string_to_datetime(list_pace[i+6]) - string_to_datetime(time)
                                pbdif = f'  (±{str(dif)[2:]})'
                                role = discord.utils.get(guild.roles, name='*NPB')
                            else:
                                role = discord.utils.get(guild.roles, name='*FIN')
                                dif = string_to_datetime(time) - string_to_datetime(list_pace[i+6])
                                pbdif = f'  (+{str(dif)[2:]})'
                          
                        # pb time
                        if event_id == 'rsg.credits' and time_to_seconds(pb_time) > time_to_seconds(time):
                          pb = f'FPB'
                        else:
                          pb = f'PB'

                        # item tracker
                        if ender_pearl_count:
                            item += f'{discord.utils.get(guild.emojis, name=get_emoji_name('ender_pearl'))} {ender_pearl_count}  '
                        if blaze_rod_count:
                            item += f'{discord.utils.get(guild.emojis, name=get_emoji_name('blaze_rod'))} {blaze_rod_count}  '
                        item = item.strip()

                        # write message
                        message = (
                            f'## {discord.utils.get(guild.emojis, name=get_emoji_name(event_id))}  {pbtitle}{time} - {convert_to_eventname(event_id)}\n'
                            f'**{pb} - {list_pace[i + 6]}{pbdif}**\n'
                            f'{convert_to_twitchlink(nickname, live_account)}    {convert_to_statslink(world_id)}    {convert_to_unix_time(dt_now, '00:00:00')}\n'
                        )
                        if item:
                            message += f'{item}\n'
                        if role is not None:
                            message += (
                                f'-# <@&{role.id}>'
                            )
                        else:
                            message += '-# role not found'

                        # choose send channel
                        if role and 'PB' in role.name:
                            channel = get_channel_by_name(guild, 'pb-pace')
                        else:
                            channel = get_channel_by_name(guild, 'not-pb-pace')
                        
                        # send message
                        if channel is not None:
                            await channel.send(message)

                        # save event id and igt in world id
                        sent_world_ids[world_id] = [event_id, max_igt]

            # loop delay
            await asyncio.sleep(10)

        except Exception as e:
            print(f"An error occurred: {e}. Retrying in 60 seconds...")
            await asyncio.sleep(60)


# Commands
@client.command(name='updatepace', description='特定のユーザーのPBペースを更新します')
async def updatepace(ctx: discord.ApplicationContext, mcid: str, ss: str, blind: str, eyespy: str, ee: str, pb: str):
  await ctx.defer()

  # get all pace
  list_pace = await get_all_pace()
  if list_pace == -1:
    # log
    print(f'updatepace: not exist pacemanbot-runner-pbpaces channel')
    # set embed
    embed = discord.Embed(title='# pacemanbot-runner-pbpaces が存在しません', color=discord.Colour.magenta())
    # response
    await ctx.respond(embed=embed)
    return
  # log
  print(f'updatepace: get all pace')
  print(f'list_pace: {list_pace}')

  time = [ss, blind, eyespy, ee, pb]
  timesplit = []

  # check time
  for l in range(5):
    for i in range(len(time[l])):
      dummy = time[l]
      if dummy[i] not in ['0','1','2','3','4','5','6','7','8','9',':']:
        # log
        print(f'updatepace: not in 0-9 or :')
        print(f'time[{l}]: {time}')
        # set embed
        embed = discord.Embed(title='タイムが不正です', color=discord.Colour.magenta())
        embed.add_field(name='SS/Blind/EyeSpy/EE/PB',value=f'{time[0]}/{time[1]}/{time[2]}/{time[3]}/{time[4]}', inline=False)
        embed.add_field(name='Tips!',value=f'タイムは半角数字と半角コロンで構成する必要があります', inline=False)
        # response
        await ctx.respond(embed=embed)
        return
    if len(time[l]) == 1:
      dummy = re.findall('1|2|3|4|5|6|7|8|9|:', time[l])
    elif len(time[l]) == 2 or len(time[l]) == 4 or len(time[l]) == 5:
      dummy = re.findall('00|01|02|03|04|05|06|07|08|09|10|11|12|13|14|15|16|17|18|19|20|21|22|23|24|25|26|27|28|29|30|31|32|33|34|35|36|37|38|39|40|41|42|43|44|45|46|47|48|49|50|51|52|53|54|55|56|57|58|59|0|1|2|3|4|5|6|7|8|9|:', time[l])
    else:
      # log
      print(f'updatepace: incorrect string')
      print(f'time[{l}]: {time}')
      # set embed
      embed = discord.Embed(title='タイムが不正です', color=discord.Colour.magenta())
      embed.add_field(name='SS/Blind/EyeSpy/EE/PB',value=f'{time[0]}/{time[1]}/{time[2]}/{time[3]}/{time[4]}', inline=False)
      embed.add_field(name='Tips!',value=f'タイムは以下のフォーマットのいずれかに沿う必要があります\n・m (mm)\n・m:ss (mm:ss)', inline=False)
      # response
      await ctx.respond(embed=embed)
      return
    
    if len(dummy) == 1 and dummy[0] != ':' and int(dummy[0]) < 60:
      timesplit.append(time[l])
    elif len(time[l]) == 4 and re.search(':', time[l]) == 1:
      timesplit.append(time[l])
    elif len(dummy) == 3 and dummy[0] != ':' and dummy[1] == ':' and dummy[2] != ':' and int(dummy[0]) < 60 and int(dummy[2]) < 60:
      timesplit.append(time[l])
    else:
      # log
      print(f'updatepace: incorrect string')
      print(f'time[{l}]: {time}')
      print(f'dummy: {dummy}')
      # set embed
      embed = discord.Embed(title='タイムが不正です', color=discord.Colour.magenta())
      embed.add_field(name='SS/Blind/EyeSpy/EE/PB',value=f'{time[0]}/{time[1]}/{time[2]}/{time[3]}/{time[4]}', inline=False)
      embed.add_field(name='Tips!',value=f'タイムがフォーマットに沿っているか確認する\nタイムが60秒/分を超えていないか確認する', inline=False)
      # response
      await ctx.respond(embed=embed)
      return

  if not time[0] <= time[1] <= time[2] <= time[3] < time[4]:
    if len(time[l]) != 5:
      # log
      print(f'updatepace: time order is incorrect')
      print(f'ss, blind, eyespy, ee, pb: {time[0]}, {time[1]}, {time[2]}, {time[3]}, {time[4]}')
      # set embed
      embed = discord.Embed(title='PBペースの順序が不正です', color=discord.Colour.magenta())
      embed.add_field(name='SS/Blind/EyeSpy/EE/PB',value=f'{time[0]}/{time[1]}/{time[2]}/{time[3]}/{time[4]}', inline=False)
      embed.add_field(name='Tips!',value=f'入力したタイムが間違っていないか確認する', inline=False)
      # response
      await ctx.respond(embed=embed)
      return

  # check mcid
  for l in range(len(mcid)):
    if mcid[l] not in ['A','B','C','D','E','F','G','H','I','J','K','L','M','N','O','P','Q','R','S','T','U','V','W','X','Y','Z','a','b','c','d','e','f','g','h','i','j','k','l','m','n','o','p','q','r','s','t','u','v','w','x','y','z','0','1','2','3','4','5','6','7','8','9','-','_']:
      # log
      print(f'updatepace: not in A-Z or 0-9 or - or _')
      print(f'mcid: {mcid}')
      # set embed
      embed = discord.Embed(title='MCIDが不正です', color=discord.Colour.magenta())
      embed.add_field(name='MCID',value=f'{mcid}', inline=False)
      embed.add_field(name='Tips!',value=f'MCIDは英数と記号で構成する必要があります', inline=False)
      # response
      await ctx.respond(embed=embed)
      return

  # update pace
  for l in range(0, len(list_pace), 7):
    if list_pace[l] == mcid:
      # log
      print(f'updatepace: before -> {list_pace[l]}/{list_pace[l+1]}/{list_pace[l+2]}/{list_pace[l+3]}/{list_pace[l+4]}/{list_pace[l+5]}/{list_pace[l+6]}')
      print(f'updatepace: after  -> {mcid}/{list_pace[l+1]}/{time[0]}/{time[1]}/{time[2]}/{time[3]}/{time[4]}')
      # set embed
      embed = discord.Embed(title='PBペースを更新しました！', color=discord.Colour.teal())
      embed.add_field(name='[Before] MCID : SS/Blind/EyeSpy/EE/PB', value=f'{list_pace[l]} : {list_pace[l+2]}/{list_pace[l+3]}/{list_pace[l+4]}/{list_pace[l+5]}/{list_pace[l+6]}', inline=False)
      embed.add_field(name='[After] MCID : SS/Blind/EyeSpy/EE/PB', value=f'{mcid} : {time[0]}/{time[1]}/{time[2]}/{time[3]}/{time[4]}', inline=False)

      # update pace
      # list_pace[l] = mcid
      # list_pace[l+1] = fs
      list_pace[l+2] = time[0]
      list_pace[l+3] = time[1]
      list_pace[l+4] = time[2]
      list_pace[l+5] = time[3]
      list_pace[l+6] = time[4]

      # edit all pace
      await set_all_pace(format_pace(list_pace))
      # response
      await ctx.respond(embed=embed)
      break
    elif l == len(list_pace)-7:
      # log
      print(f'updatepace: mcid not exist')
      # set embed
      embed = discord.Embed(title='MCIDが存在しませんでした', color=discord.Colour.magenta())
      embed.add_field(name='MCID',value=f'{mcid}', inline=False)
      embed.add_field(name='Tips!',value=f'入力したMCIDが間違っていないか確認する', inline=False)
      # response
      await ctx.respond(embed=embed)
      return


@client.command(name='updatemcid', description='特定のユーザーのMCIDを更新します')
async def updatemcid(ctx: discord.ApplicationContext, mcid: str, newmcid: str):
  await ctx.defer()

  # get all pace
  list_pace = await get_all_pace()
  if list_pace == -1:
    # log
    print(f'updatemcid: not exist pacemanbot-runner-pbpaces channel')
    # set embed
    embed = discord.Embed(title='# pacemanbot-runner-pbpaces が存在しません', color=discord.Colour.magenta())
    # response
    await ctx.respond(embed=embed)
    return
  # log
  print(f'updatemcid: get all pace')
  print(f'list_pace: {list_pace}')

  ids = [mcid, newmcid]

  # check mcid
  for l in range(2):
    dummy = ids[l]
    for i in range(len(ids[l])):
      if dummy[i] not in ['A','B','C','D','E','F','G','H','I','J','K','L','M','N','O','P','Q','R','S','T','U','V','W','X','Y','Z','a','b','c','d','e','f','g','h','i','j','k','l','m','n','o','p','q','r','s','t','u','v','w','x','y','z','0','1','2','3','4','5','6','7','8','9','-','_']:
        # log
        print(f'updatepace: not in A-Z or 0-9 or - or _')
        print(f'mcid: {ids[l]}')
        # set embed
        embed = discord.Embed(title='MCIDが不正です', color=discord.Colour.magenta())
        embed.add_field(name='MCID',value=f'{ids[l]}', inline=False)
        embed.add_field(name='Tips!',value=f'MCIDは英数と記号で構成する必要があります', inline=False)
        # response
        await ctx.respond(embed=embed)
        return
      
  # check already exist
  for l in range(0, len(list_pace), 7):
    if list_pace[l] == newmcid:
      # log
      print(f'updatepace: mcid already exist')
      # set embed
      embed = discord.Embed(title='すでに追加されているMCIDです', color=discord.Colour.magenta())
      embed.add_field(name='MCID',value=f'{newmcid}', inline=False)
      embed.add_field(name='Tips!',value=f'入力したMCIDが間違っていないか確認する', inline=False)
      # response
      await ctx.respond(embed=embed)
      return
    
  # update mcid
  for l in range(0, len(list_pace), 7):
    if list_pace[l] == mcid:
      # log
      print(f'updatemcid: before -> {list_pace[l]}')
      print(f'updatemcid: after  -> {newmcid}')
      # set embed
      embed = discord.Embed(title='MCIDを更新しました！', color=discord.Colour.teal())
      embed.add_field(name='[Before] MCID', value=f'{list_pace[l]}', inline=False)
      embed.add_field(name='[After] MCID', value=f'{newmcid}', inline=False)

      # update mcid
      list_pace[l] = newmcid

      # edit all pace
      await set_all_pace(format_pace(list_pace))
      # response
      await ctx.respond(embed=embed)
      break
    elif l == len(list_pace)-7:
      # log
      print(f'updatemcid: mcid not exist (pace)')
      # set embed
      embed = discord.Embed(title='MCIDが存在しませんでした', color=discord.Colour.magenta())
      embed.add_field(name='MCID',value=f'{newmcid}', inline=False)
      embed.add_field(name='Tips!',value=f'入力したMCIDが間違っていないか確認する', inline=False)
      # response
      await ctx.respond(embed=embed)
      return


@client.command(name='adduser', description='特定のユーザーを追加します')
async def adduser(ctx: discord.ApplicationContext, mcid: str, ss: str, blind: str, eyespy: str, ee: str, pb: str):
  await ctx.defer()

  # get all pace
  list_pace = await get_all_pace()
  if list_pace == -1:
    # log
    print(f'adduser: not exist pacemanbot-runner-pbpaces channel')
    # set embed
    embed = discord.Embed(title='# pacemanbot-runner-pbpaces が存在しません', color=discord.Colour.magenta())
    # response
    await ctx.respond(embed=embed)
    return
  # log
  print(f'adduser: get all pace')
  print(f'list_pace: {list_pace}')

  time = [ss, blind, eyespy, ee, pb]
  timesplit = []

  # check time
  for l in range(5):
    for i in range(len(time[l])):
      dummy = time[l]
      if dummy[i] not in ['0','1','2','3','4','5','6','7','8','9',':']:
        # log
        print(f'adduser: not in 0-9 or :')
        print(f'time[{l}]: {time}')
        # set embed
        embed = discord.Embed(title='タイムが不正です', color=discord.Colour.magenta())
        embed.add_field(name='SS/Blind/EyeSpy/EE/PB',value=f'{time[0]}/{time[1]}/{time[2]}/{time[3]}/{time[4]}', inline=False)
        embed.add_field(name='Tips!',value=f'タイムは半角数字と半角コロンで構成する必要があります', inline=False)
        # response
        await ctx.respond(embed=embed)
        return
    if len(time[l]) == 1:
      dummy = re.findall('1|2|3|4|5|6|7|8|9|:', time[l])
    elif len(time[l]) == 2 or len(time[l]) == 4 or len(time[l]) == 5:
      dummy = re.findall('00|01|02|03|04|05|06|07|08|09|10|11|12|13|14|15|16|17|18|19|20|21|22|23|24|25|26|27|28|29|30|31|32|33|34|35|36|37|38|39|40|41|42|43|44|45|46|47|48|49|50|51|52|53|54|55|56|57|58|59|0|1|2|3|4|5|6|7|8|9|:', time[l])
    else:
      # log
      print(f'adduser: incorrect string')
      print(f'time[{l}]: {time}')
      # set embed
      embed = discord.Embed(title='タイムが不正です', color=discord.Colour.magenta())
      embed.add_field(name='SS/Blind/EyeSpy/EE/PB',value=f'{time[0]}/{time[1]}/{time[2]}/{time[3]}/{time[4]}', inline=False)
      embed.add_field(name='Tips!',value=f'タイムは以下のフォーマットのいずれかに沿う必要があります\n・m (mm)\n・m:ss (mm:ss)', inline=False)
      # response
      await ctx.respond(embed=embed)
      return
    
    if len(dummy) == 1 and dummy[0] != ':' and int(dummy[0]) < 60:
      timesplit.append(time[l])
    elif len(time[l]) == 4 and re.search(':', time[l]) == 1:
      timesplit.append(time[l])
    elif len(dummy) == 3 and dummy[0] != ':' and dummy[1] == ':' and dummy[2] != ':' and int(dummy[0]) < 60 and int(dummy[2]) < 60:
      timesplit.append(time[l])
    else:
      # log
      print(f'adduser: incorrect string')
      print(f'time[{l}]: {time}')
      print(f'dummy: {dummy}')
      # set embed
      embed = discord.Embed(title='タイムが不正です', color=discord.Colour.magenta())
      embed.add_field(name='SS/Blind/EyeSpy/EE/PB',value=f'{time[0]}/{time[1]}/{time[2]}/{time[3]}/{time[4]}', inline=False)
      embed.add_field(name='Tips!',value=f'タイムがフォーマットに沿っているか確認する\nタイムが60秒/分を超えていないか確認する', inline=False)
      # response
      await ctx.respond(embed=embed)
      return

  if not time[0] <= time[1] <= time[2] <= time[3] < time[4]:
    if len(time[l]) != 5:
      # log
      print(f'adduser: time order is incorrect')
      print(f'ss, blind, eyespy, ee, pb: {time[0]}, {time[1]}, {time[2]}, {time[3]}, {time[4]}')
      # set embed
      embed = discord.Embed(title='PBペースの順序が不正です', color=discord.Colour.magenta())
      embed.add_field(name='SS/Blind/EyeSpy/EE/PB',value=f'{time[0]}/{time[1]}/{time[2]}/{time[3]}/{time[4]}', inline=False)
      embed.add_field(name='Tips!',value=f'入力したタイムが間違っていないか確認する', inline=False)
      # response
      await ctx.respond(embed=embed)
      return

  # check mcid
  for l in range(len(mcid)):
    if mcid[l] not in ['A','B','C','D','E','F','G','H','I','J','K','L','M','N','O','P','Q','R','S','T','U','V','W','X','Y','Z','a','b','c','d','e','f','g','h','i','j','k','l','m','n','o','p','q','r','s','t','u','v','w','x','y','z','0','1','2','3','4','5','6','7','8','9','-','_']:
      # log
      print(f'adduser: not in A-Z or 0-9 or - or _')
      print(f'mcid: {mcid}')
      # set embed
      embed = discord.Embed(title='MCIDが不正です', color=discord.Colour.magenta())
      embed.add_field(name='MCID',value=f'{mcid}', inline=False)
      embed.add_field(name='Tips!',value=f'MCIDは英数と記号で構成する必要があります', inline=False)
      # response
      await ctx.respond(embed=embed)
      return

  # add pace
  for l in range(0, len(list_pace), 7):
    if list_pace[i] == mcid:
      # log
      print(f'adduser: mcid not exist (pace)')
      # set embed
      embed = discord.Embed(title='すでに追加されているMCIDです', color=discord.Colour.magenta())
      embed.add_field(name='MCID',value=f'{mcid}', inline=False)
      embed.add_field(name='Tips!',value=f'入力したMCIDが間違っていないか確認する', inline=False)
      # response
      await ctx.respond(embed=embed)
      return
    elif l == len(list_pace)-7:
      # log
      print(f'adduser: add -> {mcid}/1/{time[0]}/{time[1]}/{time[2]}/{time[3]}/{time[4]}')
      # set embed
      embed = discord.Embed(title='PBペースを追加しました！', color=discord.Colour.teal())
      embed.add_field(name='MCID : SS/Blind/EyeSpy/EE/PB', value=f'{mcid} : {time[0]}/{time[1]}/{time[2]}/{time[3]}/{time[4]}', inline=False)

      # add pace
      list_pace.append(mcid)
      list_pace.append('1')
      list_pace.append(time[0])
      list_pace.append(time[1])
      list_pace.append(time[2])
      list_pace.append(time[3])
      list_pace.append(time[4])

      # edit all pace
      await set_all_pace(format_pace(list_pace))
      # response
      await ctx.respond(embed=embed)


@client.command(name='deleteuser', description='特定のユーザーを削除します')
async def deleteuser(ctx: discord.ApplicationContext, mcid: str):
  await ctx.defer()

  # get all pace
  list_pace = await get_all_pace()
  if list_pace == -1:
    # log
    print(f'deleteuser: not exist pacemanbot-runner-pbpaces channel')
    # set embed
    embed = discord.Embed(title='# pacemanbot-runner-pbpaces が存在しません', color=discord.Colour.magenta())
    # response
    await ctx.respond(embed=embed)
    return
  # log
  print(f'deleteuser: get all pace')
  print(f'list_pace: {list_pace}')

  # check mcid
  for l in range(len(mcid)):
    if mcid[l] not in ['A','B','C','D','E','F','G','H','I','J','K','L','M','N','O','P','Q','R','S','T','U','V','W','X','Y','Z','a','b','c','d','e','f','g','h','i','j','k','l','m','n','o','p','q','r','s','t','u','v','w','x','y','z','0','1','2','3','4','5','6','7','8','9','-','_']:
      # log
      print(f'deleteuser: not in A-Z or 0-9 or - or _')
      print(f'mcid: {mcid}')
      # set embed
      embed = discord.Embed(title='MCIDが不正です', color=discord.Colour.magenta())
      embed.add_field(name='MCID',value=f'{mcid}', inline=False)
      embed.add_field(name='Tips!',value=f'MCIDは英数と記号で構成する必要があります', inline=False)
      # response
      await ctx.respond(embed=embed)
      return
      
  # delete user
  for l in range(0, len(list_pace), 7):
    if list_pace[l] == mcid:
      # log
      print(f'deleteuser: delete -> {mcid}')
      # set embed
      embed = discord.Embed(title='ユーザーを削除しました！', color=discord.Colour.teal())
      embed.add_field(name='MCID : SS/Blind/EyeSpy/EE/PB', value=f'{list_pace[l]} : {list_pace[l+2]}/{list_pace[l+3]}/{list_pace[l+4]}/{list_pace[l+5]}/{list_pace[l+6]}', inline=False)

      # delete user
      for n in range(7):
        dummy = list_pace.pop(l)

       # edit all pace
      await set_all_pace(format_pace(list_pace))
      # response
      await ctx.respond(embed=embed)
      return
    elif l == len(list_pace)-7:
      # log
      print(f'deleteuser: mcid not exist (pace)')
      # set embed
      embed = discord.Embed(title='MCIDが存在しませんでした', color=discord.Colour.magenta())
      embed.add_field(name='MCID',value=f'{mcid}', inline=False)
      embed.add_field(name='Tips!',value=f'入力したMCIDが間違っていないか確認する', inline=False)
      # response
      await ctx.respond(embed=embed)
      return


@client.command(name='getpace', description='特定のユーザーのPBペースを取得します')
async def getpace(ctx: discord.ApplicationContext, mcid: str):
  await ctx.defer()

  # get all pace
  list_pace = await get_all_pace()
  if list_pace == -1:
    # log
    print(f'getpace: not exist pacemanbot-runner-pbpaces channel')
    # set embed
    embed = discord.Embed(title='# pacemanbot-runner-pbpaces が存在しません', color=discord.Colour.magenta())
    # response
    await ctx.respond(embed=embed)
    return
  # log
  print(f'getpace: get all pace')
  print(f'list_pace: {list_pace}')

  # check mcid
  for l in range(len(mcid)):
    if mcid[l] not in ['A','B','C','D','E','F','G','H','I','J','K','L','M','N','O','P','Q','R','S','T','U','V','W','X','Y','Z','a','b','c','d','e','f','g','h','i','j','k','l','m','n','o','p','q','r','s','t','u','v','w','x','y','z','0','1','2','3','4','5','6','7','8','9','-','_']:
      # log
      print(f'getpace: not in A-Z or 0-9 or - or _')
      print(f'mcid: {mcid}')
      # set embed
      embed = discord.Embed(title='MCIDが不正です', color=discord.Colour.magenta())
      embed.add_field(name='MCID',value=f'{mcid}', inline=False)
      embed.add_field(name='Tips!',value=f'MCIDは英数と記号で構成する必要があります', inline=False)
      # response
      await ctx.respond(embed=embed)
      return
      
  # get pace
  for l in range(0, len(list_pace), 7):
    if list_pace[l] == mcid:
      # log
      print(f'getpace: get -> {list_pace[l]}/{list_pace[l+1]}/{list_pace[l+2]}/{list_pace[l+3]}/{list_pace[l+4]}/{list_pace[l+5]}/{list_pace[l+6]}')
      # set embed
      embed = discord.Embed(title='PBペースを取得しました！', color=discord.Colour.teal())
      embed.add_field(name='MCID : SS/Blind/EyeSpy/EE/PB', value=f'{list_pace[l]} : {list_pace[l+2]}/{list_pace[l+3]}/{list_pace[l+4]}/{list_pace[l+5]}/{list_pace[l+6]}', inline=False)
      # response
      await ctx.respond(embed=embed)
      return
    elif l == len(list_pace)-7:
      # log
      print(f'getpace: mcid not exist')
      # set embed
      embed = discord.Embed(title='MCIDが存在しませんでした', color=discord.Colour.magenta())
      embed.add_field(name='MCID',value=f'{mcid}', inline=False)
      embed.add_field(name='Tips!',value=f'入力したMCIDが間違っていないか確認する', inline=False)
      # response
      await ctx.respond(embed=embed)
      return


# Defs
def get_channel_by_name(guild, name):
  for channel in guild.text_channels:
    if channel.name == name:
      return channel
  print(f'channel {name} not found.')
  return None


async def fetch_data():
  url = 'https://paceman.gg/api/ars/liveruns'
  async with aiohttp.ClientSession() as session:
    async with session.get(url) as response:
      if response.status == 200:
        return await response.json()
      else:
        print(f'failed to fetch data. status code: {response.status}')
        return None


def convert_to_unix_time(date: datetime.datetime, duration) -> str:
    if isinstance(duration, datetime.timedelta):
        total_seconds = int(duration.total_seconds())
        hours, remainder = divmod(total_seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        duration_str = f'{hours}:{minutes:02}:{seconds:02}'
    elif isinstance(duration, str):
        parts = list(map(int, duration.split(':')))
        if len(parts) == 2:
            hours = 0
            minutes = parts[0]
            seconds = parts[1]
        elif len(parts) == 3:
            hours = parts[0]
            minutes = parts[1]
            seconds = parts[2]
        else:
            raise ValueError('invalid duration format. use hh:mm:ss or mm:ss.')
    else:
        raise ValueError('invalid duration type. must be str or datetime.timedelta.')

    end_date = date + datetime.timedelta(days=0, hours=hours, minutes=minutes, seconds=seconds)

    date_tuple = (end_date.year, end_date.month, end_date.day, end_date.hour, end_date.minute, end_date.second)

    return f'<t:{int(time.mktime(datetime.datetime(*date_tuple).timetuple()))}:R>'


# https://gist.github.com/himoatm/e6a189d9c3e3c4398daea7b943a9a55d
def string_to_datetime(string):
    return datetime.datetime.strptime(string, '%M:%S')


def convert_to_hh_mm_ss(time):
    if isinstance(time, int):
      time = str(time)

    seconds = int(time[:-3])
    milliseconds = int(time[-3:])
    
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    seconds = seconds % 60
    
    if hours > 0:
        return f'{hours:02}:{minutes:02}:{seconds:02}'
    else:
        return f'{minutes:02}:{seconds:02}'


def time_to_seconds(time_str):
    parts = list(map(int, time_str.split(':')))
    if len(parts) == 2:
        return parts[0] * 60 + parts[1]
    elif len(parts) == 3:
        return parts[0] * 3600 + parts[1] * 60 + parts[2]
    return 0


def convert_to_eventname(eventid):
    event_names = {
        'rsg.enter_nether': 'Enter Nether',
        'rsg.enter_bastion': 'Enter Bastion',
        'rsg.enter_fortress': 'Enter Fortress',
        'rsg.first_portal': 'First Portal',
        'rsg.enter_stronghold': 'Enter Stronghold',
        'rsg.enter_end': 'Enter End',
        'rsg.credits': 'Finish'
    }
    return event_names.get(eventid, 'Unknown Event')


def get_emoji_name(eventid):
    event_names = {
        'rsg.enter_nether': 'nether',
        'rsg.enter_bastion': 'bastion',
        'rsg.enter_fortress': 'fortress',
        'rsg.first_portal': 'portal',
        'rsg.enter_stronghold': 'sh',
        'rsg.enter_end': 'end',
        'rsg.credits': 'credits',
        'ender_pearl': 'ender_pearl',
        'blaze_rod': 'blaze_rod'
    }
    return event_names.get(eventid, 'red_circle')


def convert_to_twitchlink(name, account):
  if account != None:
    return f'[{name}](<https://www.twitch.tv/{account}>)'
  return f'Offline - {name}'


def convert_to_statslink(worldid):
  return f'[ [Stats](<https://paceman.gg/stats/run/{worldid}>) ]'


async def get_all_pace():
  ch_name = 'pacemanbot-runner-pbpaces'
  for channel in client.get_all_channels():
    if channel.name == ch_name:
      pace = await channel.fetch_message(channel.last_message_id)
      split = pace.content.replace('```\n', '').replace('\n```', '').replace('\n', '/').replace(' : ', '/')
      list_pace = split.split('/')
      return list_pace
  return -1


async def set_all_pace(content):
  ch_name = 'pacemanbot-runner-pbpaces'
  for channel in client.get_all_channels():
    if channel.name == ch_name:
      pace = await channel.fetch_message(channel.last_message_id)
      print('sended paces')
      await channel.send(content)
      print('deleted paces')
      await pace.delete()


def format_pace(list):
  content = ''
  for l in range(0, len(list), 7):
    content += f'\n{list[l]} : {list[l+1]}/{list[l+2]}/{list[l+3]}/{list[l+4]}/{list[l+5]}/{list[l+6]}'
  return f'```\n{content[1:]}\n```'


def format_name(list):
  content = ''
  for l in range(0, len(list), 6):
    content += f'\n{list[l]}:{list[l+1]}/{list[l+2]}/{list[l+3]}/{list[l+4]}/{list[l+5]}'
  return f'```\n{content[1:]}\n```'


# Server and TOKEN
server_thread()
client.loop.create_task(send_nicknames_periodically())
client.run(TOKEN)