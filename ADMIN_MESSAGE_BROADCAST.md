# Admin Message Broadcast System

## Overview
Broadcast important messages to all participant pages using modal overlays. Messages are polled every 30 seconds with automatic jitter to prevent server overload.

## Quick Start

### Creating a Broadcast Message

1. **Access Admin Interface**
   - Navigate to: http://localhost:8000/admin/accounts/adminmessage/
   - Login with admin credentials

2. **Configure Message**
   - **Überschrift** (Heading): Short title (optional)
   - **Nachricht** (Content): Message text (optional)
   - **Hintergrundfarbe** (Background Color): Use color picker or enter hex code (default: #ef4444 red)

3. **Save**
   - Click "Sichern" (Save) to activate the message
   - Page stays on the edit screen with success message
   - All participants will see it within ~30 seconds
   - **Note**: Only one save button shown (singleton pattern)

### Deactivating Message

- Clear both heading AND content fields
- Empty messages won't display to participants

### Updating Message

- Edit any field and save
- Participants who already dismissed the old message will see the updated one

## Architecture

### Backend

- **Model**: `accounts.models.AdminMessage` (singleton pattern)
- **API Endpoint**: `/api/admin-message/` (participant authentication required)
- **Caching**: 5-minute cache (300 seconds)
- **Response Format**:
  ```json
  {
    "ok": true,
    "message": {
      "heading": "Important Announcement",
      "content": "Competition paused for 15 minutes",
      "background_color": "#ef4444",
      "updated_at": 1768567699.472486
    }
  }
  ```
  Or `{"ok": true, "message": null}` if no active message.

### Frontend

- **Polling Module**: `static/js/admin_message_poll.js`
- **Poll Interval**: 30 seconds
- **Initial Jitter**: 5-10 seconds (prevents thundering herd)
- **Tracking**: localStorage key `admin_message_seen_timestamp`
- **Display**: Full-screen modal overlay with backdrop
- **Dismissal**: Click close button (×) or click backdrop

### Active Pages

The polling system is active on all 8 participant pages:
1. Dashboard (`/dashboard/`)
2. Ergebnisse (`/dashboard/ergebnisse/`)
3. Live-Scoreboard (`/dashboard/live-scoreboard/`)
4. Regelwerk (`/regelwerk/`)
5. Hilfe (`/support/`)
6. Einstellungen (`/settings/`)
7. Laufplan (`/dashboard/laufplan/`)
8. (All pages using `participant_section_base.html`)

## Performance

### Load Characteristics
- **300 concurrent clients**: ~10 requests/second steady state
- **Cache hit rate**: 99% (5-min cache, 30s polls)
- **Database queries**: ~0.1/second
- **Network efficiency**: Jitter prevents synchronized polling

### Monitoring

Check Django logs for:
- `INFO: Admin message cached` - Initial cache population
- Failed authentications trigger `logger.warning`

## Configuration

Edit `web_project/settings/config.py` → `FrontendConfig`:

```python
ADMIN_MESSAGE_POLL_INTERVAL_MS: int = 30000      # Poll every 30s
ADMIN_MESSAGE_POLL_JITTER_MIN_MS: int = 5000     # Min initial delay 5s
ADMIN_MESSAGE_POLL_JITTER_MAX_MS: int = 10000    # Max initial delay 10s
```

## Technical Details

### Modal Styling
- **Backdrop**: `rgba(0,0,0,0.6)` overlay, z-index 9998
- **Modal**: Centered, max-width 500px, z-index 9999
- **Background**: Uses admin-selected color from database
- **Text**: White color, pre-wrap formatting
- **Responsive**: 90% max-width on mobile

### Cache Invalidation
- Automatic on save (see `AdminMessage.save()` method)
- Cache key: `'admin_message'`
- Timeout: 300 seconds (matches `SETTINGS_CACHE_TIMEOUT`)

### localStorage Schema
```javascript
{
  "admin_message_seen_timestamp": "1768567699.472486"
}
```

## Troubleshooting

### Message Not Appearing

1. **Check message has content**:
   ```python
   from accounts.models import AdminMessage
   msg = AdminMessage.objects.first()
   print(msg.has_content())  # Should be True
   ```

2. **Clear cache**:
   ```python
   from django.core.cache import cache
   cache.delete('admin_message')
   ```

3. **Check browser console** for polling errors

### Message Appears Repeatedly

- Check localStorage in browser DevTools
- Clear `admin_message_seen_timestamp` key
- Verify `updated_at` timestamp is being tracked correctly

### High Server Load

- Increase poll interval in config.py
- Verify cache is working (check Django logs)
- Monitor cache hit rate with Django debug toolbar

## Security

- **Authentication**: Requires participant session (`@participant_required`)
- **XSS Protection**: Modal uses `textContent` (not innerHTML)
- **Singleton Pattern**: Prevents multiple simultaneous messages
- **Rate Limiting**: Jitter prevents coordinated attacks

## Rollback

### Quick Disable
Clear heading + content in admin (polling continues harmlessly)

### Full Removal
```bash
# 1. Remove script tags from templates
# 2. Remove URL pattern from web_project/urls.py
# 3. Delete static/js/admin_message_poll.js
# 4. Create migration to drop table
python3 manage.py makemigrations accounts
python3 manage.py migrate
```

## Testing

Run verification test:
```bash
source .venv/bin/activate
python3 manage.py shell < verification_test.py
```

All tests should pass:
- ✓ Model and database
- ✓ Admin registration
- ✓ API endpoint
- ✓ Caching mechanism
- ✓ Frontend configuration
- ✓ JavaScript module

## Browser Testing

1. Open DevTools → Network tab, filter "admin-message"
2. Verify polling requests every ~30 seconds
3. Create/update message in admin
4. Modal should appear within 30 seconds
5. Dismiss modal → localStorage updated
6. Reload page → Modal doesn't reappear (same message)

---

**Implementation Date**: January 16, 2026
**Status**: ✓ Production Ready
**Documentation**: Complete
