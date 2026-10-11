#!/usr/bin/env python3
"""Runs the birthday bot against a throwaway server and talks to it.

    python3 smoke.py <folder with cordedd and corded-cli>

The kit (corded_bot.py) is looked for where CORDED_BOT_KIT says, in ./kit, or
in a bot-kit folder beside this repository.
"""
import base64
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request
from http.server import BaseHTTPRequestHandler, HTTPServer

bin_dir = os.path.abspath(sys.argv[1])
repo = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
bots = repo
for kit in (os.environ.get("CORDED_BOT_KIT", ""), repo, os.path.join(repo, "kit"), os.path.join(repo, "..", "bot-kit")):
    if kit and os.path.exists(os.path.join(kit, "corded_bot.py")):
        sys.path.insert(0, os.path.abspath(kit))
        os.environ["CORDED_BOT_KIT"] = os.path.abspath(kit)
        break
from corded_bot import Bot, Message, mentioned_names  # noqa: E402,F401

os.environ["CORDED_CLI"] = os.path.join(bin_dir, "corded-cli")

def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def main():
    tmp = tempfile.mkdtemp(prefix="corded-bots-")
    started = []
    try:
        port, hook_port, model_port = free_port(), free_port(), free_port()
        address = f"127.0.0.1:{port}"
        started.append(subprocess.Popen([os.path.join(bin_dir, "cordedd"), "--port", str(port), "--data",
                                         os.path.join(tmp, "server"), "--owner", "alice"],
                                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL))
        time.sleep(1)

        # A person, written with the same kit, who records what she is told.
        heard = []
        alice = Bot(vault=os.path.join(tmp, "alice"), username="alice", is_bot=False, hear_bots=True)
        alice.on_message(lambda m: heard.append((m.sender, m.body)))
        heard_where = []
        alice.on_message(lambda m: heard_where.append((m.room_id, m.body)))
        alice.connect(address)
        threading.Thread(target=alice.run, daemon=True).start()

        def wait_for(what, test, seconds=25, among=heard):
            end = time.time() + seconds
            while time.time() < end:
                for item in list(among):
                    if test(item):
                        return item
                time.sleep(0.2)
            raise AssertionError(f"did not hear {what}; heard {among}")

        def person(name):
            """Someone else, who keeps the messages and files that reach them."""
            texts, files = [], []
            someone = Bot(vault=os.path.join(tmp, name), username=name, is_bot=False, hear_bots=True)
            someone.on_message(texts.append)
            someone.on_file(files.append)
            someone.connect(address)
            threading.Thread(target=someone.run, daemon=True).start()
            return someone, texts, files

        def bot_process(*words):
            p = subprocess.Popen([sys.executable, *words], cwd=bots, stdout=subprocess.PIPE, text=True)
            started.append(p)
            line = p.stdout.readline()   # each bot prints one line when it is connected
            assert "connected" in line, line
            return p

        # The birthday bot. It is told that today is 17 May 2026.
        def birthdays(*more):
            return bot_process("birthday_bot.py", address, "--today", "2026-05-17", "--tick", "2",
                               "--join-delay", "2", "--vault", os.path.join(tmp, "birthdays"), *more)
        running = birthdays()
        carol, carol_heard, carol_files = person("carol")
        asked = wait_for("to be asked for a birthday", lambda m: m.sender == "birthdays" and "birthday bot" in m.body,
                         among=carol_heard)
        assert asked.direct, "the question was not in a direct chat"
        # Carol's first words in a new chat make her client send her profile
        # there by itself; the answers to what she asks next must still be hers.
        carol.say(asked.room_id, "17th of May 2004")
        assert "members" in carol.request({"cmd": "member_list"})
        assert isinstance(carol.profile_of(alice.me), dict)
        assert carol.dm("birthdays") == asked.room_id
        wait_for("the date read back", lambda m: m.sender == "birthdays" and "Got it: **17 May 2004**" in m.body,
                 among=carol_heard)
        assert any("That's today!" in m.body for m in carol_heard)
        wait_for("a wish in the direct chat", lambda m: m.direct and m.body == "🎂 **Happy birthday, carol!** 22 today.",
                 among=carol_heard)
        wait_for("a wish in the channel",
                 lambda item: item == ("birthdays", "🎂 **Happy birthday**, @carol! (22 today.)"))
        its = next(m for m in carol.members().values() if m["username"] == "birthdays")
        profile = carol.profile_of(its["user_id"])
        assert its["display_name"] == "Birthday Bot" and its["bot"] and "birthdays" in profile["bio"]
        assert base64.b64decode(profile["picture"]) == open(os.path.join(bots, "birthday_bot.png"), "rb").read()
        print("ok  birthday bot: asks a new member, reads the date, wishes in the direct chat and in #general; "
              "has a name, a line about itself and a picture")

        # A birthday in the profile, without a year; and a bot that joins is not asked.
        dave, dave_heard, dave_files = person("dave")
        dave.request({"cmd": "set_profile", "birthday": "05-17"})
        wait_for("a wish from the profile", lambda item: item == ("birthdays", "🎂 **Happy birthday**, @dave!"))
        bot_process(os.path.join(os.environ["CORDED_BOT_KIT"], "command_bot.py"), address, "latecomer", os.path.join(tmp, "latecomer"))
        alice.say("#general", "!birthdays")
        wait_for("the list", lambda item: item[0] == "birthdays" and "- **carol**: 17 May (today 🎂)" in item[1]
                 and "- **dave**: 17 May (today 🎂)" in item[1])
        assert not [item for item in heard if "birthday bot" in item[1]], "someone here before the bot was asked"
        wait_for("the bot to say what it saw in the profile", lambda m: m.sender == "birthdays" and
                 "I see from your profile that your birthday is **17 May**" in m.body and "Tell me" not in m.body,
                 among=dave_heard)
        print("ok  birthday bot: a birthday from the profile, seen and not asked for; the list of those coming")
        # The other words it knows in a direct chat.
        with_bot = dave.dm("birthdays")
        for said, answer in (("when", "I have **17 May**, from your profile."),
                             ("17/05", "I can't tell the day from the month"),
                             ("private", "I'll wish you here only"),
                             ("what?", "I didn't understand that. I have your birthday as **17 May**, "
                                       "from your profile."),
                             ("forget", "Your profile says **17 May**, and I go by that"),
                             ("help", "## 🎂 Birthday Bot\n"
                                      "I wish people a happy birthday on the day, in a direct chat and in #general.\n\n"
                                      "**Your birthday:** 17 May, from your profile\n"
                                      "**Wished in #general:** no, here only\n\n"
                                      "**To change it, send me a date**\n- `05-17`"),
                             ("!help", "**Your birthday:** 17 May, from your profile")):
            dave.say(with_bot, said)
            wait_for(f"the answer to {said}", lambda m: m.sender == "birthdays" and answer in m.body, among=dave_heard)
        del heard[:]
        alice.say("#general", "!birthdays")
        listed = wait_for("the list again", lambda item: item[0] == "birthdays" and "**carol**: 17 May" in item[1])
        assert "dave" not in listed[1], "someone who asked to be wished privately was listed"
        # Someone who is asked first and fills in the profile afterwards is told that it was seen.
        erin, erin_heard, _ = person("erin")
        wait_for("erin to be asked", lambda m: "Tell me your birthday" in m.body, among=erin_heard)
        erin.say(erin.dm("birthdays"), "help")
        wait_for("help for someone it knows nothing of", lambda m: "**Your birthday:** not set yet" in m.body
                 and "**To set it, send me a date**" in m.body and "**Wished in #general:** yes" in m.body,
                 among=erin_heard)
        alice.say("#general", "!help")
        wait_for("help in a channel", lambda item: item[0] == "birthdays" and "## 🎂 Birthday Bot" in item[1]
                 and "`!birthdays`" in item[1] and "Your birthday" not in item[1])
        erin.request({"cmd": "set_profile", "birthday": "1999-12-25"})
        wait_for("the bot to notice", lambda m: m.direct and
                 "I see your birthday in your profile now: **25 December 1999**" in m.body, among=erin_heard)
        erin.say(erin.dm("birthdays"), "24 dec")
        wait_for("the two dates to be weighed",
                 lambda m: "Got it: **24 December**. I'll wish you a happy birthday then. Your profile says "
                           "**25 December 1999**; I'll go by what you told me here." in m.body, among=erin_heard)
        print("ok  birthday bot: help (in a chat and in a channel), when, private, forget, a date it cannot read, "
              "a profile filled in later, "
              "and the list leaves private people out")

        time.sleep(6)   # past the wait before a newcomer is asked, and a few looks at the clock
        running.terminate()
        running.wait()
        running = birthdays()
        time.sleep(6)
        assert not [item for item in heard if "Happy birthday" in item[1]], "wished again after a restart"
        running.terminate()
        running.wait()
        birthdays("--greet-existing")
        late = wait_for("alice to be asked when told to ask everyone", lambda item: "birthday bot" in item[1])
        alice.say(alice.dm("birthdays"), "No.")
        wait_for("no to be taken", lambda item: item[0] == "birthdays" and "I won't ask" in item[1])
        heard.remove(late)
        time.sleep(4)
        assert len([m for m in carol_heard if "birthday bot" in m.body]) == 1, "carol was asked twice"
        assert not [item for item in heard if "birthday bot" in item[1]], "alice was asked twice"
        people = json.load(open(os.path.join(tmp, "birthdays", "store.json")))["people"]
        asked_ids = {user for user, kept in people.items() if kept.get("asked")}
        names = {user: member["username"] for user, member in alice.members().items()} | {alice.me: "alice"}
        assert asked_ids == {carol.me, alice.me, dave.me, erin.me}, ("a bot was written to",
                                                   sorted(names.get(user, user) for user in asked_ids))
        assert people[alice.me].get("no") and people[dave.me].get("private")
        print("ok  birthday bot: nobody wished or asked twice after a restart; old members asked only with "
              "--greet-existing; bots never")

        # What only the owner and those with the Manage bots permission may tell it.
        to_bot = {who: who.dm("birthdays") for who in (alice, carol, dave)}
        carol.say(to_bot[carol], "list")
        wait_for("a refusal", lambda m: "Only the server's owner and people with the **Manage bots**" in m.body,
                 among=carol_heard)
        alice.say(to_bot[alice], "list")
        wait_for("the owner's list", lambda item: "**Birthdays I know (3)**" in item[1]
                 and "- **carol** (`carol`): 17 May; told me, wished in 2026" in item[1]
                 and "- **dave** (`dave`): 17 May; from the profile, wished in 2026, private" in item[1]
                 and "**No birthday yet:** alice (said no, asked)" in item[1] and "2004" not in item[1])
        del heard[:]
        alice.say(to_bot[alice], "reset wishes @carol")
        wait_for("the reset", lambda item: "Done: **carol** can be wished again this year." in item[1])
        wait_for("carol wished again", lambda item: item == ("birthdays", "🎂 **Happy birthday**, @carol! (22 today.)"))
        assert len([m for m in carol_heard if m.direct and "Happy birthday" in m.body]) == 2

        made = alice.request({"cmd": "create_role", "name": "botkeeper", "permissions": ["manage_bots"]})
        alice.request({"cmd": "grant_role", "username": "carol", "role": "botkeeper"})
        for _ in range(20):   # a role just given takes a moment to be known everywhere
            if carol.may(carol.me):
                break
            time.sleep(0.5)
        assert carol.may(carol.me), f"the role did not arrive: {made}"
        assert alice.may(alice.me) and not dave.may(dave.me)
        carol.say(to_bot[carol], "set @erin 17 may")
        wait_for("a date set by someone with the role", lambda m: "Done: **erin**'s birthday is **17 May**." in m.body,
                 among=carol_heard)
        wait_for("erin wished", lambda item: item == ("birthdays", "🎂 **Happy birthday**, @erin!"))
        carol.say(to_bot[carol], "help")
        wait_for("help with the part for managers", lambda m: "**Because you manage bots here**" in m.body
                 and "`reset wishes`" in m.body, among=carol_heard)
        before = len(dave_heard)
        dave.say(to_bot[dave], "help")
        said = wait_for("help without it", lambda m: dave_heard.index(m) >= before and "## 🎂 Birthday Bot" in m.body
                        and "Wished in" in m.body, among=dave_heard)
        assert "manage bots" not in said.body

        del heard[:]
        alice.say(to_bot[alice], "reset dave")
        wait_for("everything about dave forgotten", lambda item: "forgotten everything about **dave**" in item[1])
        wait_for("dave wished again, no longer privately",
                 lambda item: item == ("birthdays", "🎂 **Happy birthday**, @dave!"))
        alice.say(to_bot[alice], "ask everyone")
        wait_for("the count", lambda item: "Done: I wrote to 1 person." in item[1])
        assert len([m for m in dave_heard if "I see from your profile" in m.body]) == 2
        alice.say(to_bot[alice], "reset asked")
        wait_for("everyone unasked", lambda item: "people reset. I ask each of them when they next join" in item[1])
        alice.say(to_bot[alice], "ask @alice")
        wait_for("no respected", lambda item: "**alice** told me not to ask, so I won't." in item[1])
        alice.say(to_bot[alice], "reset wishes @nobody")
        wait_for("an unknown name", lambda item: "I don't know anyone called **nobody** here." in item[1])
        print("ok  birthday bot: list, reset, set and ask for the owner and for a role with Manage bots; "
              "refused to everyone else")

        # The channel it announces in: #general until told otherwise, and kept through a restart.
        alice.say(to_bot[alice], "channel")
        wait_for("where it announces", lambda item: "Birthdays are announced in **#general**." in item[1])
        alice.say(to_bot[alice], "channel #nowhere")
        wait_for("a channel it cannot see", lambda item: "I can't see a channel called **#nowhere**" in item[1]
                 and "`#general`" in item[1])
        alice.request({"cmd": "create_channel", "name": "parties"})
        time.sleep(3)
        alice.say(to_bot[alice], "channel parties")
        wait_for("the change", lambda item: "Done: birthdays are announced in **#parties** from now on." in item[1])
        alice.say(to_bot[alice], "time")
        wait_for("when it wishes", lambda item: "I wish people at **09:00**, by the clock" in item[1])
        alice.say(to_bot[alice], "time half past")
        wait_for("a time it cannot read", lambda item: "I can't read that as a time of day." in item[1])
        alice.say(to_bot[alice], "time 7:30 am")
        wait_for("the new time", lambda item: "Done: I wish people at **07:30** from now on" in item[1])
        for running_bot in started[-3:]:
            if "birthday_bot.py" in running_bot.args:
                running_bot.terminate()
                running_bot.wait()
        birthdays()
        alice.say(to_bot[alice], "channel")
        wait_for("the choice kept", lambda item: "Birthdays are announced in **#parties**." in item[1])
        alice.say(to_bot[alice], "time")
        wait_for("the time kept", lambda item: "I wish people at **07:30**, by the clock" in item[1])
        alice.say(to_bot[alice], "reset wishes @carol")
        wait_for("a wish in the new channel", lambda item: item == (alice.room_id("#parties"),
                 "🎂 **Happy birthday**, @carol! (22 today.)"), among=heard_where)
        print("ok  birthday bot: the channel is #general and the time 09:00 until a manager changes them, "
              "and the changes are kept")

        print("PASS")
    finally:
        for p in started:
            p.terminate()
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    main()

