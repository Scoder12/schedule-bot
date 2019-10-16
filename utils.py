import discord
from menu import MenuItem
import datetime
import config
import logging


async def next_dt(today=None):
    """Returns the datetime of the next tuesday or thursday
    """
    if today is None:
        today = datetime.datetime.now()
    wd = today.isoweekday()
    if wd == 2 or wd == 4:
        return today
    if wd < 2: # can only be 1
        offset = 2 - wd
    elif wd < 4:
        offset = 4 - wd
    else: # more than 4
        # find end of week, then add to to get to tuesday
        offset = 2 + (7 - wd)
    return today + datetime.timedelta(days=offset)


def get_channel_members(channel_id):
	return config.bot.get_channel(channel_id).members


def check_user_id(channel, arg):
	try:
		member = channel.guild.get_member(int(arg))
		if member is not None:
			return member
	except ValueError:
		pass


def check_mention(channel, arg):
	if arg.startswith('<@') and arg[-1] == '>':
		if arg[2] == '!':
			user_id = arg[3:-1]
		else:
			user_id = arg[2:-1]
		try:
			member = channel.guild.get_member(int(user_id))
			if member is not None:
				return member
		except ValueError:
			pass


def check_name_with_discrim(channel, arg):
	member = discord.utils.find(
		lambda m: str(m).lower() == arg.lower(),
		channel.members
	)
	return member


def check_name_without_discrim(channel, arg):
	member = discord.utils.find(
		lambda m: m.name.lower == arg.lower(),
		channel.members
	)
	return member


def check_nickname(channel, arg):
	member = discord.utils.find(
		lambda m: m.display_name.lower() == arg.lower(),
		channel.members
	)
	return member


def check_name_starts_with(channel, arg):
	member = discord.utils.find(
		lambda m: m.name.lower().startswith(arg.lower()),
		channel.members
	)
	return member


def check_nickname_starts_with(channel, arg):
	member = discord.utils.find(
		lambda m: m.display_name.lower().startswith(arg.lower()),
		channel.members
	)
	return member


def check_name_contains(channel, arg):
	member = discord.utils.find(
		lambda m: arg.lower() in m.name.lower(),
		channel.members
	)
	return member


def check_nickname_contains(channel, arg):
	member = discord.utils.find(
		lambda m: arg.lower() in m.display_name.lower(),
		channel.members
	)
	return member


async def parse_member(channel, arg):
    if arg[0] == '@':
        arg = arg[1:]
    # Check user id
    member = check_user_id(channel, arg)
    if member is not None:
        return member

    # Check mention
    member = check_mention(channel, arg)
    if member is not None:
        return member

    # Name + discrim
    member = check_name_with_discrim(channel, arg)
    if member is not None:
        return member

    # Name
    member = check_name_with_discrim(channel, arg)
    if member is not None:
        return member

    # Nickname
    member = check_nickname(channel, arg)
    if member is not None:
        return member

    # Name starts with
    member = check_name_starts_with(channel, arg)
    if member is not None:
        return member

    # Nickname starts with
    member = check_nickname_starts_with(channel, arg)
    if member is not None:
        return member

    # Name contains
    member = check_name_contains(channel, arg)
    if member is not None:
        return member

    # Nickname contains
    member = check_nickname_contains(channel, arg)
    if member is not None:
        return member


def _key(j, *ks, raise_e=False, default=''):
    for k in ks:
        if k not in j:
            if raise_e:
                j[k] # cause error
            else:
                return default
        j = j[k]
    return j


async def process_courses(courses):
    logger = logging.getLogger("COURSES")
    items = []
    for c in courses:
        method = ''
        # get rid of everything that we can't schedule
        if _key(c, 'blockedReason') is not None:
            logger.warn(f'blocked for {c["blockedReason"]!r}')
            continue
        if _key(c, 'preventStudentSelfScheduling'):
            method = 'request'
            if _key(c, 'preventStudentRequesting'):
                continue
        if not _key(c, 'isOpenForScheduling'):
            logger.warn(f'not open for scheduling: {_key(c, "isOpenForScheduling")}')
            continue
        if not _key(c, 'courseId') or not _key(c, 'periodId'):
            logger.warn('no course or period')
            continue
        
        # now we know it is a valid course, construct MenuItem
        title = _key(c, 'courseName', default="(no coursename)")
        lname = _key(c, 'staffLastName', default="(no last name)")
        fname = _key(c, 'staffFirstName', default="(no first name)")
        room = '(Room ' + c['courseRoom'] + ')' if _key(c, 'courseRoom') else '(no room)'
        maxseats = _key(c, 'maxNumberStudents', default="?")
        taken = _key(c, 'numberOfAppointments', default="?")
        if not maxseats or not taken:
            avail = '?'
        try:
            avail = maxseats - taken
        except:
            avail = '?'
        status = "REQUESTED " if _key(c, 'appointmentRequestCourseId') == c['courseId'] else ""
        item = MenuItem(f"{status}{title}", # title
            f"{lname}, {fname} in {room} | {taken} seats taken, "
            f"{avail} seats left", # description
            {
                'reqCid': _key(c, 'appointmentRequestCourseId'),
                'cid': c['courseId'],
                'period': c['periodId'],
                'method': method,
                'name': _key(c, 'courseName')
            }) # value that will be returned
        items.append(item)
    return items
