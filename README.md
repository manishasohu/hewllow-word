# AdBot - Advanced Multi-Service Telegram Forwarding System

**A sophisticated bot that orchestrates multiple independent services, each with multiple userbots, forwarding messages across Telegram groups with strict category-based routing and group-level distribution.**

---

## 📋 Table of Contents

1. [System Architecture](#system-architecture)
2. [Multi-Service Design](#multi-service-design)
3. [Multiple Userbots Per Service](#multiple-userbots-per-service)
4. [Message Flow & Distribution](#message-flow--distribution)
5. [Execution Model](#execution-model)
6. [Category System](#category-system)
7. [Flow Diagrams](#flow-diagrams)
8. [Database Schema](#database-schema)
9. [Configuration](#configuration)

---

## 🏗️ System Architecture

### Core Components

```
AdBot
├── ServiceOrchestrator (Main Coordinator)
│   ├── Service 1
│   │   ├── BotCoordinator
│   │   └── Bots [1, 2, 3, ...]
│   ├── Service 2
│   │   ├── BotCoordinator
│   │   └── Bots [1, 2, 3, ...]
│   └── Service N
│       ├── BotCoordinator
│       └── Bots [1, 2, 3, ...]
├── IsolationManager (Service Isolation)
├── MessageFlowCoordinator (Message Handling)
└── UserbotManager (Bot Session Management)
```

### Key Data Structures

#### ServiceInfo
Each service has:
- **service_name**: Unique service identifier (e.g., "instagram", "twitter")
- **service_id**: Unique internal ID
- **bots**: List of BotInfo objects (multiple userbots)
- **state**: ServiceState (IDLE, INITIALIZING, RUNNING, COMPLETED, ERROR)
- **groups_by_level**: Groups organized by distribution level
- **current_cycle_id**: Current forwarding cycle identifier
- **messages_sent**: Total messages sent in current cycle

#### BotInfo
Each userbot has:
- **bot_id**: Unique bot ID
- **bot_label**: Human-readable label
- **assigned_category**: The ONLY category this bot can forward (strict enforcement)
- **groups**: List of groups assigned to this bot (exclusive ownership)
- **state**: BotState (IDLE, RUNNING, COMPLETED, ERROR)
- **current_group_level**: Current processing level
- **messages_sent**: Messages sent by this bot
- **last_activity_time**: Last activity timestamp

---

## 🔄 Multi-Service Design

### Service Independence & Isolation

The system supports **unlimited parallel services** with complete isolation:

```
┌─────────────────────────────────────────────────────┐
│           ServiceOrchestrator                        │
│                                                       │
│  ┌────────────────┐  ┌────────────────┐             │
│  │   Service 1    │  │   Service 2    │  ...        │
│  │  (Instagram)   │  │   (Twitter)    │             │
│  │                │  │                │             │
│  │ Bots: [1,2,3]  │  │ Bots: [4,5]    │             │
│  │ Groups: [A,B]  │  │ Groups: [C,D]  │             │
│  │ Category: IG   │  │ Category: TW   │             │
│  └────────────────┘  └────────────────┘             │
│                                                       │
│   All services run SIMULTANEOUSLY                   │
│   NO interaction between services                   │
│   NO group sharing                                  │
│   NO bot sharing                                    │
└─────────────────────────────────────────────────────┘
```

### Isolation Guarantees

**IsolationManager** ensures:

| Property | Guarantee |
|----------|-----------|
| **Group Exclusivity** | Each group assigned to exactly ONE service |
| **Bot Exclusivity** | Each bot assigned to exactly ONE service |
| **Category Exclusivity** | Each bot has ONE assigned category (no crossing) |
| **Execution Isolation** | Services run in parallel without interference |
| **Database Isolation** | Separate cycle records per service |

### Service Registration Example

```python
# Service 1: Instagram bot forwarding IG content
service1_bots = [
    BotInfo(bot_id=1, bot_label="InstagramBot1", assigned_category="instagram", groups=[{...}])
]
orchestrator.register_service("Instagram", "service_1", service1_bots, groups=[...])

# Service 2: Twitter bot forwarding Twitter content
service2_bots = [
    BotInfo(bot_id=4, bot_label="TwitterBot1", assigned_category="twitter", groups=[{...}])
]
orchestrator.register_service("Twitter", "service_2", service2_bots, groups=[...])

# Both services start simultaneously and run in parallel
await orchestrator.start_all_services()
```

---

## 🤖 Multiple Userbots Per Service

### Bot Coordination Model

When a service has **multiple userbots**, they coordinate using **round-robin scheduling** across group levels:

```
                    Service with 3 Bots
                    ───────────────────
                    
           ┌─────────────┬─────────────┬─────────────┐
           │   Bot 1     │   Bot 2     │   Bot 3     │
           │ (Category)  │ (Category)  │ (Category)  │
           └─────────────┴─────────────┴─────────────┘
                    ↓         ↓         ↓
           Groups: [A,B]  [C,D]    [E,F]
                (Exclusive  (Exclusive  (Exclusive
                  Division)   Division)   Division)
```

### Multi-Bot Execution Flow

**FOR EACH GROUP LEVEL** (1, 2, 3, ...):
```
GROUP LEVEL 1
├─ Bot 1 → Sends to Groups [A, B] at Level 1
├─ Bot 2 → Sends to Groups [C, D] at Level 1
├─ Bot 3 → Sends to Groups [E, F] at Level 1
└─ All bots wait for Level 1 completion

GROUP LEVEL 2
├─ Bot 1 → Sends to Groups [A, B] at Level 2
├─ Bot 2 → Sends to Groups [C, D] at Level 2
├─ Bot 3 → Sends to Groups [E, F] at Level 2
└─ All bots wait for Level 2 completion

... (continues for all levels)
```

### Round-Robin Bot Selection

Within a service, bots are selected sequentially in a circular pattern:

```
BotCoordinator Round-Robin Sequence:
Cycle 1: Bot[0] → Bot[1] → Bot[2] → Bot[0] → Bot[1] → Bot[2] ...
         ↓       ↓       ↓       ↓       ↓       ↓
        Send   Send   Send   Send   Send   Send
        Grp1  Grp2   Grp3   Grp4   Grp5  Grp6
```

### Bot State Management

Each bot has a state machine:

```
    ┌─────────┐
    │  IDLE   │
    └────┬────┘
         │ Service starts
         ↓
    ┌─────────┐
    │ RUNNING │ ◄───── Per-message delays applied
    └────┬────┘           Group join delays applied
         │ All groups processed
         ↓
    ┌─────────┐
    │COMPLETED├─────► Service cycle complete
    └─────────┘
    
         × ERROR (on failure)
```

### Multi-Bot Coordination Example

**Service "Instagram" with 3 userbots:**

```
BotInfo {
  bot_id: 1001,
  bot_label: "InstaBot_1",
  assigned_category: "instagram",      ✅ STRICT: Only Instagram messages
  groups: [GroupA, GroupB],            ✅ Exclusive groups
  state: RUNNING,
  current_group_level: 1,
  messages_sent: 45
}

BotInfo {
  bot_id: 1002,
  bot_label: "InstaBot_2",
  assigned_category: "instagram",      ✅ STRICT: Only Instagram messages
  groups: [GroupC, GroupD],            ✅ Exclusive groups
  state: RUNNING,
  current_group_level: 1,
  messages_sent: 48
}

BotInfo {
  bot_id: 1003,
  bot_label: "InstaBot_3",
  assigned_category: "instagram",      ✅ STRICT: Only Instagram messages
  groups: [GroupE, GroupF],            ✅ Exclusive groups
  state: RUNNING,
  current_group_level: 1,
  messages_sent: 42
}

Total messages by Instagram service: 135
```

---

## 📊 Message Flow & Distribution

### Group Level System

Groups are organized into **sequential processing levels** to ensure distributed load:

```
GROUPS (Total 10)
├─ Level 1: [GroupA]        (1st to receive messages)
├─ Level 2: [GroupB, GroupC] (2nd to receive messages)
├─ Level 3: [GroupD, GroupE] (3rd to receive messages)
└─ Level 4: [GroupF-J]      (4th to receive messages)

Why? Prevents flood: Groups get messages in staggered waves
Not all groups bombarded at once
```

### Message Routing Based on Category

**Category Keywords** are extracted from messages to determine routing:

```python
CATEGORY_KEYWORDS = {
    "instagram": ["instagram", "insta", "ig", "dm", "story", ...],
    "twitter": ["twitter", "x.com", "tweet", "retweet", ...],
    "telegram": ["telegram", "tg", "channel", "group", ...],
    "tiktok": ["tiktok", "tik tok", "tt", "viral", ...],
    "youtube": ["youtube", "video", "yt", "subscribe", ...],
}
```

### Message Flow for Single Service

```
                    Message Arrives
                          │
                          ↓
            ┌─────────────────────────────┐
            │ Extract Keywords from Text  │
            └─────────────────────────────┘
                          │
                    ┌─────┴─────┐
                    ↓           ↓
              Instagram?    Twitter?
              (Bot Group    (Different
              Instagram)    Service)
                    │           │
         ┌──────────┴─┐         │
         │            │         │
      Bot 1A        Bot 1B    Bot 2A
      Send to      Send to    Send to
      Groups       Groups     Groups
      [A,B]        [C,D]      [X,Y]
       at L1        at L1      at L1
```

### Message Deduplication & Cycle Tracking

**Prevent duplicate message forwarding:**

```
Database: message_forwarding_log
├─ chat_id (destination group)
├─ userbot_id (which bot sent)
├─ message_hash (unique message identifier)
├─ category (message category)
├─ cycle_id (current forwarding cycle)
└─ timestamp

Before forwarding:
  Check: was this message already sent to this group by this bot in this cycle?
  If YES → Skip (already forwarded)
  If NO  → Forward and mark in DB
```

---

## ⚙️ Execution Model

### System-Wide Flow

```
┌──────────────────────────────────────────┐
│ orchestrator.start_all_services()        │
│ (Async entry point)                      │
└────────────┬─────────────────────────────┘
             │
             ↓
     ┌───────────────────┐
     │ Verify all        │
     │ services isolated │
     └────────┬──────────┘
              │
         ┌────┴────┐
         ↓         ↓      ↓
      Service1  Service2  Service N
      (Task 1)  (Task 2)  (Task N)
         │         │        │
         │ ─ ─ ─ ─ ┴ ─ ─ ─ ┤
         │   All run in     │
         │   PARALLEL       │
         │   simultaneously │
         └ ─ ─ ─ ─┬ ─ ─ ─ ┘
                  ↓
        ┌──────────────────┐
        │ Wait for ALL     │
        │ services to      │
        │ complete         │
        └────────┬─────────┘
                 ↓
        ┌──────────────────┐
        │ Print final      │
        │ statistics       │
        └──────────────────┘
```

### Single Service Execution

```
START: _run_service(service_id)
       │
       ├─ Set state = RUNNING
       ├─ Create cycle record
       └─ Get total group levels
              │
              ├─ FOR EACH GROUP LEVEL (sequential)
              │  │
              │  ├─ FOR EACH BOT (round-robin)
              │  │  │
              │  │  ├─ Get next bot in sequence
              │  │  ├─ Get bot's EXCLUSIVE groups at this level
              │  │  ├─ Get messages for bot's ASSIGNED CATEGORY
              │  │  ├─ Create ForwardingContext
              │  │  │  └─ message_category = bot.assigned_category
              │  │  │
              │  │  └─ execute_forward_sequence()
              │  │     │
              │  │     ├─ FOR EACH GROUP (bot's exclusive groups)
              │  │     │  │
              │  │     │  ├─ Acquire send lock
              │  │     │  ├─ Check if already forwarded (dedup)
              │  │     │  ├─ Handle forum topics if needed
              │  │     │  ├─ Send message via Telethon
              │  │     │  ├─ Apply per-message delay
              │  │     │  ├─ Log to database
              │  │     │  └─ Release send lock
              │  │     │
              │  │     └─ RETURN (total_sent, total_failed)
              │  │
              │  ├─ Wait for all bots to complete level
              │  └─ Advance to next level
              │
              └─ State = COMPLETED
                 RETURN
```

### Within-Group Message Distribution

```
single_group = {
    'id': 123456789,
    'title': 'My Group',
    'link': 't.me/mygroup',
    'is_forum': True,
    'topics': [...]  (if forum)
}

FOR EACH MESSAGE in messages:
  ├─ Check deduplication
  │  └─ is_message_already_forwarded(group_id, msg_hash, category, cycle)?
  │
  ├─ IF forum group:
  │  ├─ Match message to forum topic by category keywords
  │  ├─ forward_to_forum_group()
  │  │  └─ Send message to matched topic or general topic
  │  └─ Apply per-message delay
  │
  ├─ ELSE if regular group:
  │  ├─ forward_to_regular_group()
  │  │  └─ Send message to group
  │  └─ Apply per-message delay
  │
  ├─ Mark message as forwarded in DB
  │  └─ INSERT into message_forwarding_log
  │      (chat_id, bot_id, msg_hash, category, cycle_id)
  │
  └─ NEXT MESSAGE
```

---

## 🏷️ Category System

### Strict Category Enforcement

**Each bot's assigned_category is IMMUTABLE and EXCLUSIVE:**

```
Bot Assignment Rules:
┌─────────────────────────────────────────┐
│ 1. Bot belongs to ONE service           │
│ 2. Bot has ONE assigned category        │
│ 3. Bot ONLY forwards its category msgs  │
│ 4. Bot NEVER forwards default category  │
│ 5. Bot has EXCLUSIVE group set          │
│ 6. NO bot can access another bot's grps │
│ 7. NO bot can exceed its category       │
└─────────────────────────────────────────┘
```

### Category Detection

```python
def detect_message_category(message_text: str) -> str:
    """Detect which category a message belongs to"""
    text_lower = message_text.lower()
    
    # Check each category
    for category, keywords in CATEGORY_KEYWORDS.items():
        if any(keyword in text_lower for keyword in keywords):
            return category
    
    return "default"  # Fallback if no category matched

# Example
message = "Check my new Instagram post! insta.com/..."
category = detect_message_category(message)
# Returns: "instagram"
```

### Category-Based Bot Filtering

```
Message arrives with category = "instagram"

Look for bots with: assigned_category == "instagram"

Found Bots:
├─ Bot 1001: assigned_category = "instagram" ✅
├─ Bot 1002: assigned_category = "instagram" ✅
└─ Bot 1003: assigned_category = "instagram" ✅

Bots to SKIP:
├─ Bot 2001: assigned_category = "twitter" ❌
├─ Bot 3001: assigned_category = "youtube" ❌
└─ Bot 4001: assigned_category = "tiktok" ❌

Only Instagram bots forward this message
```

---

## 🎯 Flow Diagrams

### Diagram 1: Complete Multi-Service Execution Architecture

```
┌──────────────────────────────────────────────────────────────────────┐
│                    ORCHESTRATOR.START_ALL_SERVICES()                 │
└───────────────────────┬──────────────────────────────────────────────┘
                        │
            ┌───────────┴───────────┐
            ↓                       ↓
    ┌─────────────────────┐  ┌─────────────────────┐
    │ Verify Isolation    │  │ Initialize Services│
    │ ✓ No group sharing  │  │ ✓ Assign bots      │
    │ ✓ No bot sharing    │  │ ✓ Assign groups    │
    └────┬────────────────┘  └────┬────────────────┘
         │                         │
         └────────────┬────────────┘
                      ↓
        ┌─────────────────────────────────┐
        │ LAUNCH ALL SERVICES IN PARALLEL │
        └────┬────────────────────────────┘
             │
    ┌────────┼────────┬────────────┐
    ↓        ↓        ↓            ↓
┌─────┐  ┌─────┐  ┌─────┐    ┌─────────┐
│Svc1 │  │Svc2 │  │Svc3 │ ..│SvcN    │
│Task │  │Task │  │Task │    │Task    │
└──┬──┘  └──┬──┘  └──┬──┘    └────┬───┘
   │        │        │             │
   └────────┼────────┼─────────────┘
            │        │ (All tasks run in parallel)
            ↓
    ┌──────────────────────┐
    │  SERVICE EXECUTION   │
    │ (see section below)  │
    └──────────────────────┘
            │
            ↓
    ┌──────────────────────┐
    │ AWAIT ALL COMPLETION │
    └────┬─────────────────┘
         │
         ↓
    ┌──────────────────────┐
    │ PRINT FINAL RESULTS  │
    │ - Total messages     │
    │ - Messages per bot   │
    │ - Execution time     │
    │ - Success rate       │
    └──────────────────────┘
```

### Diagram 2: Single Service Execution (Detailed)

```
┌─────────────────────────────────────────────────┐
│       START SERVICE EXECUTION (_run_service)    │
└──────────────────┬──────────────────────────────┘
                   │
                   ├─ Set service state = RUNNING
                   ├─ Create cycle record in DB
                   └─ Get all group levels
                   │
        ┌──────────┴──────────────────────────┐
        │                                      │
        ↓ FOR EACH GROUP LEVEL (sequential)   │
    ┌──────────────────────────┐              │
    │ GROUP LEVEL X            │              │
    │ (e.g., 1, 2, 3...)       │              │
    └───────┬──────────────────┘              │
            │                                  │
            ├─ FOR EACH BOT (round-robin)     │
            │  │                               │
            │  ↓                               │
            │ ┌────────────────────────────┐  │
            │ │ BOT N in sequence          │  │
            │ │ ├─ Get next bot (round-r) │  │
            │ │ ├─ Mark state = RUNNING    │  │
            │ │ └─ Get assigned groups     │  │
            │ │    at current level        │  │
            │ └───────┬────────────────────┘  │
            │         │                        │
            │         ├─ Get messages for     │
            │         │  BOT'S CATEGORY       │
            │         ├─ Create ForwardingCtx │
            │         ├─ FOR EACH MESSAGE:    │
            │         │  │                    │
            │         │  ├─ Check dedup DB    │
            │         │  ├─ If not forwarded: │
            │         │  │  ├─ Get next group │
            │         │  │  ├─ Acquire lock   │
            │         │  │  ├─ Send via Tele  │
            │         │  │  ├─ Log to DB      │
            │         │  │  ├─ Apply delay    │
            │         │  │  └─ Release lock   │
            │         │  │                    │
            │         │  └─ NEXT MESSAGE      │
            │         │                        │
            │         └─ Mark bot completed   │
            │            for this level       │
            │                                  │
            └─ Wait: All bots done with      │
               this level?                    │
               If NO: sleep & retry           │
               If YES: continue               │
               │                               │
               └────────────────────────────┬─┘
                                            │
                                      [NEXT LEVEL]
                                            │
                           ┌────────────────┘
                           │
                           ↓  (After all levels)
                    ┌────────────────┐
                    │ Set state =    │
                    │ COMPLETED      │
                    └────────────────┘
                           │
                           ↓
                    ┌────────────────┐
                    │ RETURN from    │
                    │ _run_service() │
                    └────────────────┘
```

### Diagram 3: How Services Handle Multiple Userbots

```
┌──────────────────────────────────────────────────────────────┐
│               SERVICE "INSTAGRAM" (3 Userbots)               │
└──────────────────────────────────────────────────────────────┘

At GROUP LEVEL 1:
┌─────────────────────────────────────────────────────────────┐
│ SEQUENTIAL BOT PROCESSING (Round-Robin)                     │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  Step 1: Get Bot 1                                          │
│  ├─ bot_id: 1001                                            │
│  ├─ assigned_category: "instagram"                          │
│  ├─ assigned_groups: [GroupA, GroupB]                       │
│  └─ Get Instagram messages →                               │
│     Send to GroupA (Level 1) + delay                        │
│     Send to GroupB (Level 1) + delay                        │
│     Mark completed for level 1                              │
│                                                               │
│  Step 2: Get Bot 2                                          │
│  ├─ bot_id: 1002                                            │
│  ├─ assigned_category: "instagram"                          │
│  ├─ assigned_groups: [GroupC, GroupD]                       │
│  └─ Get Instagram messages →                               │
│     Send to GroupC (Level 1) + delay                        │
│     Send to GroupD (Level 1) + delay                        │
│     Mark completed for level 1                              │
│                                                               │
│  Step 3: Get Bot 3                                          │
│  ├─ bot_id: 1003                                            │
│  ├─ assigned_category: "instagram"                          │
│  ├─ assigned_groups: [GroupE, GroupF]                       │
│  └─ Get Instagram messages →                               │
│     Send to GroupE (Level 1) + delay                        │
│     Send to GroupF (Level 1) + delay                        │
│     Mark completed for level 1                              │
│                                                               │
│  WAIT: All 3 bots done with Level 1? YES ✓                 │
│  ADVANCE to Level 2                                         │
│                                                               │
└─────────────────────────────────────────────────────────────┘

At GROUP LEVEL 2:
(Same process repeats for next level)

RESULT:
  Total Instagram messages sent: 135
  - Bot 1: 45 messages
  - Bot 2: 48 messages
  - Bot 3: 42 messages
```

### Diagram 4: Message Routing by Category

```
                          Message Received
                                │
                                ↓
                    ┌─────────────────────────┐
                    │ Analyze Message Content │
                    │ Extract Keywords        │
                    └────────────┬────────────┘
                                 │
                    ┌────────────┴────────────┐
                    │                         │
                    ↓                         ↓
            Instagram Keywords?      Twitter Keywords?
            (instagram, insta, ig,    (twitter, x.com,
             dm, story, ...)          tweet, retweet, ...)
                    │                         │
                 YES│                         │NO
                    │                         │
                    ↓                         ↓
         ┌──────────────────────┐  ┌──────────────────────┐
         │ Message = "instagram"│  │ Check if Twitter     │
         │ Category             │  │ Keywords found?      │
         └──────────┬───────────┘  └──────────┬───────────┘
                    │                         │
                    ↓                         ↓ YES
         ┌──────────────────────┐  ┌──────────────────────┐
         │ Get Instagram        │  │ Message = "twitter"  │
         │ Userbots Only:       │  │ Category             │
         │ - Bot 1001 ✅        │  └──────────┬───────────┘
         │ - Bot 1002 ✅        │             │
         │ - Bot 1003 ✅        │             ↓
         │ (Skip all others)    │  ┌──────────────────────┐
         └──────────┬───────────┘  │ Get Twitter          │
                    │              │ Userbots Only:       │
                    ↓              │ - Bot 2001 ✅        │
         ┌──────────────────────┐  │ - Bot 2002 ✅        │
         │ Forward to Instagram │  │ (Skip all others)    │
         │ Groups:              │  └──────────┬───────────┘
         │ - GroupA             │             │
         │ - GroupB             │             ↓
         │ - GroupC             │  ┌──────────────────────┐
         │ - GroupD             │  │ Forward to Twitter   │
         │ - GroupE             │  │ Groups:              │
         │ - GroupF             │  │ - GroupX             │
         └──────────┬───────────┘  │ - GroupY             │
                    │              │ - GroupZ             │
                    ↓              └──────────┬───────────┘
         Dedup check: Already                 │
         sent to group X by bot Y             ↓
         in cycle Z?                   Dedup check: Already
         - YES: Skip                   sent to group? Apply
         - NO: Send & Log              logic...
                    │
                    ↓
         (Continue with remaining bots/groups)
```

---

## 💾 Database Schema

### Key Tables

**message_forwarding_log**
```sql
chat_id          INTEGER      -- Destination group ID
userbot_id       INTEGER      -- Bot that sent the message
message_hash     TEXT         -- Unique message identifier
category         TEXT         -- Message category (instagram, twitter, etc.)
cycle_id         TEXT         -- Forwarding cycle ID
sent_at          TIMESTAMP    -- When message was sent
PRIMARY KEY (chat_id, userbot_id, message_hash, cycle_id)
```

**bot_message_coordination**
```sql
chat_id          INTEGER      -- Group ID
userbot_id       INTEGER      -- Bot ID
category         TEXT         -- Message category
cycle_id         TEXT         -- Cycle ID
message_id       INTEGER      -- Message ID in Telegram
sent_at          TIMESTAMP    -- Timestamp
UNIQUE KEY (chat_id, userbot_id, category, cycle_id, message_id)
```

**forwarding_logs**
```sql
group_id         INTEGER      -- Destination group
group_title      TEXT         -- Group title for logging
success          BOOLEAN      -- Was forwarding successful?
message_id       INTEGER      -- Message ID
logged_at        TIMESTAMP    -- Log timestamp
```

---

## ⚙️ Configuration

### Environment Variables

```bash
# Bot Configuration
BOT_TOKEN=your_telegram_bot_token
OWNER_ID=your_user_id
ADMIN_USER_IDS=123456789,987654321

# Subscription
SUBSCRIPTION_DAYS=365

# Logging
LOG_GROUP_CHAT_ID=-1003154622450
TRACK_CHANNEL_ID=channel_id
ADBOT_NAME=ADBOT

# Performance
PER_MESSAGE_DELAY_MIN=30          # Delay between messages (seconds)
GROUP_JOIN_DELAY=15               # Delay before joining group (seconds)
MAX_FORWARD_RETRIES=3             # Retry attempts for failed forwards

# Features
ENABLE_AFK_REPLY=true
ENABLE_AUTO_JOIN=true
ENABLE_FORWARDING=true
ENABLE_DATABASE_WAL=true

# Database
ADBOT_DB=adbot.db                 # Database file path
ADBOT_SESSION=userbot_session     # Session file prefix
```

### Service Setup Example

```python
from adbot import ServiceOrchestrator, BotInfo, ServiceInfo

# Initialize orchestrator
orchestrator = ServiceOrchestrator(db_path="adbot.db")

# Define Service 1: Instagram with 3 bots
insta_bots = [
    BotInfo(bot_id=1001, bot_label="InstaBot_1", assigned_category="instagram"),
    BotInfo(bot_id=1002, bot_label="InstaBot_2", assigned_category="instagram"),
    BotInfo(bot_id=1003, bot_label="InstaBot_3", assigned_category="instagram"),
]

insta_groups = [
    {"id": 101, "title": "GroupA", "link": "t.me/groupa", "is_forum": False},
    {"id": 102, "title": "GroupB", "link": "t.me/groupb", "is_forum": True},
    # ... more groups
]

# Register service
orchestrator.register_service(
    service_name="Instagram",
    service_id="service_instagram",
    bots=insta_bots,
    groups=insta_groups
)

# Define Service 2: Twitter with 2 bots
twitter_bots = [
    BotInfo(bot_id=2001, bot_label="TwitterBot_1", assigned_category="twitter"),
    BotInfo(bot_id=2002, bot_label="TwitterBot_2", assigned_category="twitter"),
]

twitter_groups = [
    {"id": 201, "title": "GroupX", "link": "t.me/groupx", "is_forum": False},
    {"id": 202, "title": "GroupY", "link": "t.me/groupy", "is_forum": False},
    # ... more groups
]

# Register service
orchestrator.register_service(
    service_name="Twitter",
    service_id="service_twitter",
    bots=twitter_bots,
    groups=twitter_groups
)

# Start all services in parallel
await orchestrator.start_all_services()
```

---

## 📈 Key Features Summary

| Feature | Details |
|---------|---------|
| **Multi-Service** | Unlimited parallel independent services |
| **Multi-Bot** | Each service can have multiple userbots |
| **Round-Robin** | Bots taking turns in sequential order |
| **Group Levels** | Groups processed in waves to prevent flooding |
| **Category-Based** | Messages routed by detected category keywords |
| **Strict Isolation** | No bot/group sharing between services |
| **Deduplication** | Prevents sending same message twice |
| **Async/Await** | Full async support for non-blocking operations |
| **Forum Support** | Automatic topic matching in forum groups |
| **Retry Logic** | Automatic retry on failed forwards |
| **Database Logging** | Complete audit trail of all forwards |

---

## 🔍 Debugging & Monitoring

### View Service Status

```python
# Get specific service status
status = orchestrator.get_service_status("service_instagram")
print(f"Service: {status['service_name']}")
print(f"State: {status['state']}")
print(f"Messages sent: {status['messages_sent']}")
print(f"Bot status: {status['bot_status']}")

# Get overall system status
system_status = orchestrator.get_system_status()
print(f"Active services: {system_status['active_services']}")
print(f"Total messages: {system_status['total_messages_sent']}")
print(f"Uptime: {system_status['uptime_seconds']}s")
```

### Database Queries for Verification

```sql
-- Check all forwards in current cycle
SELECT * FROM message_forwarding_log 
WHERE cycle_id = 'cycle_1234567890_service_instagram';

-- Bot performance metrics
SELECT userbot_id, COUNT(*) as messages_sent, category
FROM message_forwarding_log
GROUP BY userbot_id, category;

-- Failed forwards
SELECT * FROM forwarding_logs 
WHERE success = 0 
ORDER BY logged_at DESC 
LIMIT 50;
```

---

**Last Updated:** April 2026  
**Version:** 1.0.0  
**Status:** Production Ready ✅
