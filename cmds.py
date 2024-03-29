"""Command handlers"""
import storage
import time
import dateparser
import schedule
import ixl
import aiohttp
import discord
import config
from menu import number_menu, period_menu
import utils
import logging

logger = logging.getLogger(__name__)


async def pong(m , *args):
    start = time.time()
    m = await m.channel.send(":ping_pong: Pong!")
    stop = time.time()
    await m.delete()
    ms = (stop - start) * 1000
    #bot = config.bot.lantency * 100
    #return f"Pong! `{ms:.0f} ms` (bot latency: `{bot:.0f}`)"
    return f":ping_pong: Pong! `{ms:.0f} ms`"



async def register(m, *args):
    args = m.content.strip().split(' ')
    if len(args) != 3:
        return f"Usage: `{config.PREFIX}register email pwd`"
    l = await m.channel.send("Loading...")
    _, email, pwd = args
    async with schedule.API(email, pwd) as api:
        try:
            await api.login()
        except schedule.APIError as e:
            await l.edit(content="Couldn\'t register: " + str(e))
            return
    
    uid = str(m.author.id)
    logger.info(f"Registering {uid}")
    await storage.register({
        'id': uid, 
        'em': email, 
        'pwd': pwd
    })
    await l.edit(content="Registered successfully")


async def cls(m, *args):
    # get original message text
    msg = " ".join(args[1:])

    # Get the date to work with
    user_part = None
    # if they specify user=something
    if 'user=' in msg:
        # get everything after date=
        i = msg.index('user=')
        user_part = msg[i + len('user='):]
        # and set msg to everything before
        msg = msg[:i].strip()
    
    if msg.replace(' ', ''):
        date = dateparser.parse(msg)
        if not date:
            return f"Invalid date: `{msg}` Perhaps you meant user=`{msg}`?"
    else:
        date = await utils.next_dt()
    
    #logger.debug(f'msg is: {msg!r}')
    # get the member we're working with
    user = None
    if user_part: # if it isn't just spaces
        if not m.guild: # its a dm
            return "Sharing can only be used in a server, this is so only approved people can use it. Thank you for understanding. "
        user = await utils.parse_member(m.channel, user_part)
        if not user:
            # logger.debug('invalid user')
            return f"Invalid user: `{user_part}`"
        # logger.debug(f'user resolved to {user.id}')
    else:
        user = m.author

    a = await schedule.api_helper(user)
    if isinstance(a, str):
        return a
    async with a as api:
        if type(api) is str:
            return api

        if user != m.author and not api.sharing:
            return f"{user} doesn't have sharing enabled. "
        
        classes = await api.get_schedule(date)
    
    # Color: #293984
    ds = date.strftime("%m/%d")
    embed = discord.Embed(title=f":calendar_spiral: Classes on {ds}", color=utils.EMBED_COLOR)
    embed.set_author(name=str(user), icon_url=user.avatar_url)
    for s in classes:
        embed.add_field(name=s['periodDescription'], value=f"{s['courseName']} {'(Room ' + s['courseRoom']+ ')' if s['courseRoom'] else '(no room)'} {'Comment: ' + s['schedulerComment']+ ')' if s['schedulerComment'] else ''}")
    return embed


async def auto(m, *args):
    if len(args) < 2:
        newpatt = newcomm = None
    else:
        newpatt = args[1].lower()
        newcomm = " ".join(args[2:])
    
    try:
        u = await storage.get(await storage.with_id(m.author.id))
    except storage.NotFound:
        return f"Please register with `{config.PREFIX}register` before running this command"
    except storage.MultipleResults:
        storage.clear(await storage.with_id(m.author.id))
        return f"An unexpected error has occurred. Please register again with `{config.PREFIX}register`"
        
    auto = u.get('auto', None)
    if type(auto) != list or len(auto) != 2:
        patt = comm = None
    else:
        patt, comm = auto
    if not newpatt:
        if not auto:
            s = "disabled"
        else:
            if patt is None or comm is None:
                s = "configured improperly"
            else:
                patt, comm = auto
                s = f"enabled for `{patt}` with comment `{comm}`"
        return f"Auto signup is {s}"
    
    if newpatt == patt and newcomm == comm:
        return "Auto signup already uses those settings. "
    u['auto'] = [newpatt, newcomm]
    await storage.register(u)
    return f"Auto signup successfully set on `{newpatt}` with comment `{newcomm}`"


async def sharing(m, *args):
    if len(args) < 2:
        val = None
    elif args[1].startswith('en'):
        val = True
    else:
        val = False
    
    msg = await m.channel.send('Loading...')

    try:
        u = await storage.get(await storage.with_id(m.author.id))
    except storage.NotFound:
        await msg.edit(content=f"Please register with `{config.PREFIX}register` before running this command")
        return
    except storage.MultipleResults:
        storage.clear(await storage.with_id(m.author.id))
        await msg.edit(content=f"An unexpected error has occurred. Please register again with `{config.PREFIX}register`")
        return
    share = bool(u.get('share', False))
    d = {
        True: 'enabled',
        False: 'disabled'
    }
    if val is None:
        await msg.edit(content=f"Sharing is {d[share]}")
        return
    
    if val == share:
        await msg.edit(content=f"Sharing is already {d[val]}")
        return
    u['share'] = val
    await storage.register(u)
    await msg.edit(content=f"Sharing successfully {d[val]}")


async def c_list(m, *args):
    if len(args) > 1:
        date = dateparser.parse(" ".join(args[1:]))
    else:
        date = await utils.next_dt()
    
    a = await schedule.api_helper(m.author)
    if isinstance(a, str):
        return a
    async with a as api:
        if type(api) is str:  # error message
            return api
        
        ds = date.strftime("%m/%d")
        if ds is None:
            return "Invalid date"
        cls = await api.get_schedule(date)
        c = [i for i in cls if str(i.get('periodId')) == '1']
        if len(c) != 1:
            raise ValueError(f"There should only be one period 1: {cls} produces {c}")
        c = c[0]
        #if c['courseName'] != 'Open Schedule':
        #    return f"You are already scheduled for {c['courseName']} on {ds}"
        
        data = await api.get_classes(date)
        
        if 'courses' not in data or not data['courses']:
            return f"You are already scheduled on {ds} (no courses)"
        
        courses = data['courses']
        menu_choices = await utils.process_courses(courses)    
        
        #logger.debug('menu_choices', menu_choices)
        if not menu_choices:
            #logger.debug(f"no valid courses!")
            return f"Got {len(courses)} courses on {ds} but none are valid"
        nm, choice = await number_menu(m, menu_choices, 
            title=f"{m.author}'s class menu for {ds} (wait for all reactions before choosing)")
        try:
            await nm.delete()
        except Exception:
            pass
        if choice is not None:
            d = choice.value
            if 'cid' not in d or 'period' not in d:
                return "Something went wrong with that choice, sorry!"
            
            name = utils._key(d, 'name', default="(unknown name)")
            pm, p = await period_menu(m, name)
            if not p:
                try:
                    await pm.delete()
                except Exception:
                    pass
                if p is False:
                    await m.channel.send(":x: cancelled")
                    return
        
            comment = f"Period {p}"
            await m.channel.send(f"Comment is {comment}")
            await api.schedule(date, d['cid'], comment, period=d['period'], 
                method=utils._key(d, 'method', default=''))
            return f"{m.author.mention}, successfully scheduled you for {name} on {ds}"
    #return f"{m.author.mention} Something went wrong. "


async def ixl_cmd(m, *args):
    a = await schedule.api_helper(m.author)
    if isinstance(a, str):
        return a
    em = a.em
    EDOM = "@" + config.getenv("EDOM")
    if not em.endswith(EDOM):
        return "Your enriching students email does not end with the proper domain. Cannot sign in to ixl. "
    user = em[:len(EDOM) - 1]
    pwd = a.pwd
    print(user)
    print(pwd)
    async with aiohttp.ClientSession() as s:
        try:
            await ixl.login(s, user, pwd)
        except Exception:
            return "Invalid login details for IXL"
        stats = await ixl.get_stats(s, "2019-08-22")
        time, answered, skills = await utils.ixl_stats_summary(stats)

        embed = discord.Embed(title="IXL stats", 
            colour=discord.Color(0x52b700))
        embed.set_image(url="https://www.ixl.com/dv3/VEBuy2opNnXK8SNo8mgb7X9STdE/yui3/site-nav/assets/icon-ixl-logo-156.png")
        embed.add_field(name="Time spent practicing", value=time, inline=False)
        embed.add_field(name="Questions answered", value=answered, inline=False)
        embed.add_field(name="Skills practiced", value=skills, inline=False)
        return embed
