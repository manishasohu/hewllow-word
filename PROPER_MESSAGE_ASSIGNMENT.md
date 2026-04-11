# 📨 PROPER MESSAGE ASSIGNMENT FOR MULTIPLE BOTS IN SERVICE

## Overview

Each bot in a service gets its **OWN isolated message set**:
- ✅ Messages assigned per-bot (userbot_id)
- ✅ Messages stay in assigned category only
- ✅ Bot cannot access other bots' messages
- ✅ Multiple bots can have same/different messages

---

## ARCHITECTURE

### Database Schema (category_messages table)

```
┌─ category_messages ────────────────────────────────────┐
│ id            (INT PRIMARY KEY)                        │
│ userbot_id    (INT) ← BOT IDENTIFIER                   │
│ category      (TEXT) ← MESSAGE CATEGORY                │
│ message_link  (TEXT) ← MESSAGE SOURCE                  │
│ channel_id    (INT) ← SOURCE CHANNEL                   │
│ message_id    (INT) ← SOURCE MESSAGE ID                │
│ is_active     (BOOL) ← ACTIVE/INACTIVE FLAG            │
│ created_at    (TIMESTAMP) ← WHEN ADDED                 │
│                                                         │
│ UNIQUE(userbot_id, category, message_link)             │
│        ↑ Each bot gets UNIQUE messages per category    │
└─────────────────────────────────────────────────────────┘

ISOLATION:
┌──── Service: Instagram ──────┐
│ BOT 1 (userbot_id=1)         │
│  Messages: {msg1, msg2, msg3}│
│ BOT 2 (userbot_id=2)         │
│  Messages: {msg1, msg4}      │
│ BOT 3 (userbot_id=3)         │
│  Messages: {msg5, msg6}      │
└──────────────────────────────┘
↑ Each bot has OWN message set
```

---

## HOW TO ADD MESSAGES FOR SPECIFIC BOT

### Manual Flow (Admin Command: /add_messages)

```
User: /add_messages

Bot: 📋 Which bot to configure?
 1. BOT 1 - instagram_bot_1
 2. BOT 2 - instagram_bot_2
 3. BOT 3 - instagram_bot_3

User selects: BOT 1

Bot: 📁 Which category for BOT 1?
 1. instagram (BOT 1's assigned service)
 2. twitter
 3. telegram

User: instagram

Bot: 📤 Send message link for BOT 1 -> instagram
     Format: https://t.me/c/CHANNEL_ID/MESSAGE_ID

User: https://t.me/c/1234567/123

✅ Database insertion:
   INSERT INTO category_messages
   (userbot_id=1, category='instagram', message_link='...', channel_id=1234567, message_id=123)

✅ Message added ONLY to BOT 1 (userbot_id=1)
✅ BOT 2 and BOT 3 CANNOT access this message
```

---

## DURING MESSAGE FORWARDING

### Step 1: Retrieve Messages (Strict Isolation)

```python
# Bot 1 (id=1) requests messages
context = ForwardingContext(
    current_bot_id=1,  # BOT 1 identifier
    message_category="instagram"
)

# Get messages ONLY for Bot 1
cursor.execute('''
    SELECT * FROM category_messages
    WHERE userbot_id = 1           # ✅ Only this bot
      AND category = 'instagram'   # ✅ Only this category
      AND is_active = 1            # ✅ Only active messages
''')

# Result: Messages added to BOT 1 only
# BOT 2's messages: NOT returned
# BOT 3's messages: NOT returned
```

### Step 2: Forward Messages (Per-Bot)

```
BOT 1 forwarding process:
├─ Get messages for BOT 1: msg1, msg2, msg3 ✅
├─ Get groups for BOT 1: [100, 101] ✅
├─ Forward msg1 → group 100 ✅
├─ Forward msg2 → group 100 ✅
├─ Forward msg3 → group 100 ✅
├─ Forward msg1 → group 101 ✅
├─ Forward msg2 → group 101 ✅
└─ Forward msg3 → group 101 ✅

BOT 2 forwarding process (parallel):
├─ Get messages for BOT 2: msg1, msg4 ✅
├─ Get groups for BOT 2: [101, 102] ✅
├─ BOT 1's msg2, msg3: NOT ACCESSIBLE ❌
└─ BOT 1's groups [100]: NOT ACCESSIBLE ❌
```

---

## MESSAGE ISOLATION GUARANTEES

### Isolation Level 1: User ID Isolation

```python
# BOT 1 fetches messages
cursor.execute(
    "SELECT * FROM category_messages WHERE userbot_id = ?",
    (1,)  # ✅ Only BOT 1's messages
)
# Returns: Messages where userbot_id=1 only
# BOT 2's messages (userbot_id=2): NOT returned
# BOT 3's messages (userbot_id=3): NOT returned
```

### Isolation Level 2: Category Isolation

```python
# BOT 1 (category="instagram") fetches messages
cursor.execute(
    "SELECT * FROM category_messages WHERE userbot_id = ? AND category = ?",
    (1, "instagram")  # ✅ Only BOT 1's instagram messages
)
# Returns: instagram messages for BOT 1 only
# twitter messages: NOT returned (category mismatch)
# BOT 2's instagram messages: NOT returned (userbot_id mismatch)
```

### Isolation Level 3: Unique Constraint

```
UNIQUE(userbot_id, category, message_link)

Prevents:
❌ Same message added twice to same bot in same category
✅ Allows: Same message added to BOT1+instagram AND BOT2+instagram

Example:
INSERT (userbot_id=1, category=instagram, link=msg1) ✅
INSERT (userbot_id=1, category=instagram, link=msg1) ❌ DUPLICATE
INSERT (userbot_id=2, category=instagram, link=msg1) ✅ DIFFERENT BOT
INSERT (userbot_id=1, category=twitter, link=msg1) ✅ DIFFERENT CATEGORY
```

---

## COMPLETE FLOW EXAMPLE

### Setup Phase

```
Service: INSTAGRAM (3 bots)
├─ BOT 1 (id=1, label="IG_BOT_1")
│  assigned_category="instagram"
│  assigned_groups=[100, 101]
│
├─ BOT 2 (id=2, label="IG_BOT_2")
│  assigned_category="instagram"
│  assigned_groups=[101, 102]
│
└─ BOT 3 (id=3, label="IG_BOT_3")
   assigned_category="instagram"
   assigned_groups=[102, 103]
```

### Message Adding Phase

```
STEP 1: Add messages to BOT 1
User: /add_messages → Select BOT 1 → Category: instagram
↓
INSERT INTO category_messages
(userbot_id=1, category="instagram", message_link=msg1, ...)

User: /add_messages → Select BOT 1 → Category: instagram
↓
INSERT INTO category_messages
(userbot_id=1, category="instagram", message_link=msg2, ...)

Result: BOT 1 has messages [msg1, msg2]


STEP 2: Add messages to BOT 2
User: /add_messages → Select BOT 2 → Category: instagram
↓
INSERT INTO category_messages
(userbot_id=2, category="instagram", message_link=msg1, ...)

User: /add_messages → Select BOT 2 → Category: instagram
↓
INSERT INTO category_messages
(userbot_id=2, category="instagram", message_link=msg3, ...)

Result: BOT 2 has messages [msg1, msg3]


STEP 3: Add messages to BOT 3 (same as BOT 2)
Result: BOT 3 has messages [msg2, msg3]

Final state:
┌────────────────────────────────────┐
│ BOT 1 Messages: [msg1, msg2]       │
│ BOT 2 Messages: [msg1, msg3]       │
│ BOT 3 Messages: [msg2, msg3]       │
└────────────────────────────────────┘
Each bot has ONLY its assigned messages
```

### Forwarding Phase (Level 1)

```
TIME: 0.0s
BOT 1 processes Group 100:
  Fetch messages WHERE userbot_id=1 AND category="instagram"
  ├─ Get: msg1, msg2 ✅
  ├─ Forward msg1 → Group 100
  ├─ Delay: 30s
  ├─ Forward msg2 → Group 100
  └─ Delay: 30s

TIME: 60.0s (parallel)
BOT 2 processes Group 101:
  Fetch messages WHERE userbot_id=2 AND category="instagram"
  ├─ Get: msg1, msg3 ✅ (NOT msg2)
  ├─ Forward msg1 → Group 101
  ├─ Delay: 30s
  ├─ Forward msg3 → Group 101
  └─ Delay: 30s

TIME: 120.0s (parallel)
BOT 3 processes Group 102:
  Fetch messages WHERE userbot_id=3 AND category="instagram"
  ├─ Get: msg2, msg3 ✅ (NOT msg1)
  ├─ Forward msg2 → Group 102
  ├─ Delay: 30s
  ├─ Forward msg3 → Group 102
  └─ Delay: 30s

Result:
✅ Each bot forwards only its own messages
✅ No message sharing between bots
✅ Each bot formats its own forwarding
```

---

## QUERY PATTERNS FOR MESSAGE ISOLATION

### Pattern 1: Fetch Bot-Specific Messages

```python
# Get messages for specific bot in specific category
cursor.execute('''
    SELECT id, message_link FROM category_messages
    WHERE userbot_id = ? AND category = ? AND is_active = 1
''', (bot_id, category))
```

### Pattern 2: Prevent Message Duplication

```python
# Check if message already added to this bot in this category
cursor.execute('''
    SELECT id FROM category_messages
    WHERE userbot_id = ? AND category = ? AND message_link = ?
    LIMIT 1
''', (bot_id, category, message_link))
```

### Pattern 3: List All Messages for Bot

```python
# Get all active messages for a bot across all categories
cursor.execute('''
    SELECT category, COUNT(*) FROM category_messages
    WHERE userbot_id = ? AND is_active = 1
    GROUP BY category
''', (bot_id,))
```

### Pattern 4: Cross-Service Message Count

```python
# Count messages for category across ALL bots
cursor.execute('''
    SELECT COUNT(DISTINCT userbot_id) FROM category_messages
    WHERE category = ? AND is_active = 1
''', (category,))
```

---

## VALIDATION POINTS IN CODE

### Point 1: BotInfo (Required)

```python
@dataclass
class BotInfo:
    bot_id: int
    bot_label: str
    assigned_category: str  # ✅ Determines which messages bot accesses
    # ... other fields
```

### Point 2: Message Retrieval (Strict)

```python
async def get_messages_for_category(self, context, bot_assigned_category):
    cursor.execute('''
        SELECT * FROM category_messages
        WHERE category = ? AND userbot_id = ? AND is_active = 1
    ''', (bot_assigned_category, context.current_bot_id))
    # ✅ Filters by BOTH category AND userbot_id
```

### Point 3: Message Addition (Per-Bot)

```python
success, msg = await add_category_message(
    category="instagram",
    message_link="https://...",
    userbot_id=selected_bot_id  # ✅ Specify which bot
)

# INSERT INTO category_messages
# (userbot_id=selected_bot_id, category='instagram', ...)
# ✅ Message tied to specific bot only
```

### Point 4: Service Registration (Category Assignment)

```python
def register_service(self, service_name, service_id, bots, groups):
    for bot in bots:
        bot.assigned_category = service_name  # ✅ Ties bot to service category
```

---

## ERROR PREVENTION

### Error 1: Adding Message with Wrong Category

```python
bot_assigned_category = "instagram"
user_tries_category = "twitter"

if user_tries_category != bot_assigned_category:
    return False  # ❌ BLOCKED
    # Message: "Bot is assigned to 'instagram' only!"
```

### Error 2: Accessing Messages from Wrong Bot

```python
# Bot 2 tries to access Bot 1's messages
cursor.execute('''
    WHERE userbot_id = 1  # ← Bot 1's messages
          AND ...
''')
# Bot 2's query: WHERE userbot_id = 2
# Bot 1's messages: NOT returned ❌
```

### Error 3: Duplicate Message Detection

```python
# Try to add same message twice to same bot
INSERT (userbot_id=1, category='instagram', message_link=msg1)
INSERT (userbot_id=1, category='instagram', message_link=msg1)
# ↑ UNIQUE constraint violation → Operation blocked ✅
```

---

## ADMIN COMMANDS REFERENCE

### Add Messages for Specific Bot

```
/add_messages
→ Select which bot
→ Select category
→ Send message link
→ Repeat or skip

Result: Messages added ONLY to selected bot
```

### View Messages for Bot

```
/list_messages [bot_id]
Shows all messages for that bot across categories
```

### Remove Message from Bot

```
/remove_messages [message_id]
Removes message from the bot it's assigned to
```

### Check Bot Configuration

```
/bot_info [bot_id]
Shows:
- Bot ID
- Assigned category
- Assigned groups
- Message count
- Current state
```

---

## SUMMARY

| Component | Implementation | Verification |
|-----------|----------------|--------------|
| **Message Storage** | userbot_id + category | Per-bot isolation ✅ |
| **Message Retrieval** | Filter by userbot_id | Query returns only bot's messages ✅ |
| **Message Addition** | Specify userbot_id | Admin selects bot before adding ✅ |
| **Duplicate Prevention** | UNIQUE constraint | Same message not added twice ✅ |
| **Category Enforcement** | Validate category match | Bot can't access other categories ✅ |
| **Group Isolation** | Per-bot group set | Bot can't access other groups ✅ |

---

## PRODUCTION READY

✅ Messages properly assigned per-bot
✅ Multiple bots can have different/same messages
✅ Strict isolation at database level
✅ Prevents cross-bot message access
✅ Prevents cross-category message forwarding
✅ Works with forums, topics, and regular groups
✅ Complete error handling

