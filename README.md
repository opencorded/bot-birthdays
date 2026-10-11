# Birthdays: asks for birthdays and wishes people on the day

When someone joins, the bot asks them once, in a direct chat, for their
birthday. If their profile already has one it does not ask: it says which day
it found and that it will wish them then, and it says so too when someone it
asked fills in their profile later. They answer there (`05-17`, `17 May`, `2004-05-17` to have their age
shown) or put it in their profile; an answer in the chat wins. On the day, at
`--at` by the clock of the machine the bot runs on, it wishes them in the
direct chat and in a channel, where it mentions them by `@name` so that they
are notified.

The channel is kept in the bot's files. It is `#general` to begin with;
`--channel '#birthdays'` chooses another when the bot is started, and from
then on those who manage bots change it with `channel #name` in a direct chat
(below). Starting the bot again with the same command does not undo that.
The time of day works the same way: `09:00` to begin with, `--at` at the
start, `time 08:30` from a manager afterwards.

In the direct chat it also understands `help` (what it has for you and
everything it knows), `when`, `forget`, `no` (never ask again), `private` (no
post in the channel) and `public`. In a channel, `!birthdays` lists the next
few and `!help` says what the bot is for. Its messages use bold, lists and
headings, which the apps draw as styling.

The server's owner, and anyone with a role that has the **Manage bots**
permission, can tell it more in a direct chat. Everyone else is refused.

| | |
|---|---|
| `list` | Every birthday it knows (day and month), where each came from, and who it has asked. |
| `channel #name` | Announce birthdays in another channel. `channel` alone says which it is now. |
| `time 08:30` | Wish people at another time of day. `time` alone says when, and what the bot's clock reads. |
| `reset wishes` | Let this year's wishes go out again; anyone whose birthday is today is wished at once. `reset wishes @name` for one person. |
| `reset asked` | Let it ask people again. `reset asked @name` for one person. |
| `reset @name` | Forget everything about one person. |
| `set @name 05-17` | Set someone's birthday. |
| `ask @name`, `ask everyone` | Send its question now. It leaves out those who said no and those who told it a date. |

People who were on the server before the bot's first run are not asked, so
that starting it does not send everyone a message at once; `--greet-existing`
asks them too. Other bots are never asked. Someone born on 29 February is
wished on the 28th in other years. If the bot was off at the set time it
wishes when it is next started that day, and nobody is wished twice in a year.

The birthdays people tell it are kept in `store.json` in the bot's folder, on
the machine it runs on, and are sent nowhere.

It shows as "Birthday Bot" with a cake for a picture (`birthday_bot.png`,
drawn in `birthday_bot.svg`); `--display-name` and `--picture` change them.

## Get it running

You need a Corded server to join, and `corded-cli`, the headless client that
comes with every Corded release ([get one here](https://github.com/AndrewCromar/corded/releases)).

```sh
git clone https://github.com/opencorded/bot-birthdays
cd bot-birthdays
./setup.sh              # fetches the bot kit into ./kit and says what else is needed
export CORDED_CLI=/path/to/corded-cli     # not needed if corded-cli is on your PATH
python3 birthday_bot.py 127.0.0.1:7443
```

The first run makes a folder holding the bot's keys and a passphrase file that
only your user can read. Keep it: it *is* the bot's account. On an invite-only
server give an invite link in place of the address. The bot can run on any
machine that reaches the server; it does not have to be the server's.

To keep it running, and to see it on a page with everything else, list it in
the [host](https://github.com/opencorded/host).

## Turning it off and on

`!NAME off` and `!NAME on`, where NAME is the bot's username, from the server's
owner or anyone whose role has **Manage bots**. Off, it stays connected but
shows as offline and hears nothing except the command that wakes it.
`!NAME status` says which it is. The choice is kept across restarts.

## What it can read

Whatever a member in its place could: every message in the channels and chats
it is in, from the moment it joined. Give it a role that sees only the
channels it needs.

## Tests

```sh
python3 tests/smoke.py /folder/with/cordedd/and/corded-cli
```

runs the bot against a throwaway server on this machine.

Part of [Corded](https://github.com/AndrewCromar/corded). Apache-2.0.
