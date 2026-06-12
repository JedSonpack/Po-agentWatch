# Agent Watch UI Design

## Goal

Agent Watch helps Codex send a completion notification to a phone and watch through Bark. The first public version should provide a local Web UI where users can customize the notification format, preview the result, test Bark delivery, and copy the Codex notify configuration they need to install manually.

The project is intended for GitHub distribution, so the repository must contain runnable app code, default templates, example configuration, and documentation. User secrets and personal notification settings must remain local and must not be committed.

## Product Direction

The notification format is watch-first. The watch notification should stay short, readable, and useful without relying on images. Phone notifications may include richer Bark options such as a Logo URL, sound, and notification level.

The default audience is Chinese-speaking users. UI copy, default notification templates, README quick-start instructions, validation messages, and installation guidance should be written first for a Chinese user context. English documentation may exist, but it must not drive the product experience.

The UI should use a single-page left/right layout:

- Left side: Bark connection settings and message template controls.
- Right side: live watch preview, live phone preview, test-send result, and manual install instructions.

## First-Version Scope

### Message Customization

Users can configure:

- Title template.
- Body template.
- Logo URL for phone notification enhancement.
- Bark server URL.
- Bark device key.
- Bark notification level.
- Bark sound.
- Maximum body length for watch readability.

The template editor supports these variables:

- `{project}`: project directory name derived from the Codex event `cwd`.
- `{summary}`: shortened Codex assistant completion message.
- `{last_input}`: shortened last user input message.
- `{cwd}`: full working directory from the Codex event.
- `{time}`: local send time.

The UI should provide variable insertion buttons so users do not need to memorize placeholder names.

### Preview

The right side should show two previews:

- Watch preview: compact title and body, with body truncation applied.
- Phone preview: title, body, and optional Logo URL treatment.

The watch preview is the primary correctness target. If content is too long, the preview should show the truncated version that would be sent.

### Bark Test Send

Users can send a test Bark notification from the UI using their local settings.

Test sends should:

- Use the same template rendering path as real Codex notifications.
- Use sample event data so the user can verify formatting before installing.
- Report success or failure in the UI.
- Avoid printing or exposing the Bark key except where the user entered it.

### Manual Codex Installation

The app must not automatically edit `~/.codex/config.toml`.

Instead, the UI should generate:

- The `notify = [...]` TOML snippet for Codex.
- A shell command example for running the notification script with a sample event.
- A short explanation of where to place the snippet.

This keeps the open-source tool transparent and avoids modifying global user configuration without direct action from the user.

## Technical Architecture

### Runtime

Use a Python local Web service. Prefer the Python standard library where practical to keep installation simple.

Recommended command shape:

```bash
python3 agent_watch.py serve
```

The service should provide:

- Static HTML, CSS, and JavaScript for the UI.
- JSON API endpoints for reading and saving local configuration.
- JSON API endpoint for rendering previews.
- JSON API endpoint for sending a Bark test notification.
- A route or API response that exposes the Codex notify snippet.

### Notification Script

The existing `notify_watch.py` behavior should be preserved and extended:

- Load Codex notify JSON events from argv or stdin.
- Ignore non-`agent-turn-complete` events.
- Render title and body from the local Agent Watch config.
- Apply body collapsing and truncation before sending.
- Send through Bark using configured server, key, level, sound, and optional Logo URL.

The script should still fail soft: missing Bark key, invalid config, or network errors should not break Codex.

### Configuration

Repository files:

- Default template config.
- Example config without secrets.
- README instructions.

Local user files:

- `.agent-watch/config.json` for user settings.

The repository should include `.agent-watch/` in `.gitignore`, while still allowing committed examples outside that ignored directory.

Configuration shape should be explicit and easy to validate:

```json
{
  "bark": {
    "server": "https://api.day.app",
    "key": "",
    "level": "timeSensitive",
    "sound": "bell",
    "icon": ""
  },
  "message": {
    "title_template": "Codex 已完成：{project}",
    "body_template": "{summary}",
    "max_body_chars": 160
  }
}
```

## Error Handling

The UI should show clear errors for:

- Missing Bark key during test send.
- Invalid Bark server URL.
- Invalid Logo URL.
- Failed Bark HTTP request.
- Invalid template variable names.
- Configuration save failures.

The notify script should log concise messages and exit with status `0` for recoverable notification failures so Codex task completion is not affected.

## Testing Strategy

The implementation plan should include:

- Unit tests for template rendering, text collapsing, truncation, and unknown variables.
- Unit tests for config loading and default merging.
- A dry-run or mocked Bark send test.
- Manual browser verification of the single-page UI.
- Manual local test of `notify_watch.py` with a sample `agent-turn-complete` event.

## Out of Scope for First Version

- Hosting uploaded local Logo images.
- Automatically editing `~/.codex/config.toml`.
- Conditional template logic.
- Multiple notification providers.
- GitHub Pages-only deployment.
- User account or cloud sync.

## Acceptance Criteria

- A user can clone the repository and start the local Web UI with one documented command.
- A user can edit title/body templates, insert supported variables, set a Logo URL, and see watch and phone previews update.
- A user can save local settings to an ignored config file.
- A user can send a Bark test notification from the UI.
- A user can copy a generated Codex notify snippet instead of the tool modifying global Codex config.
- `notify_watch.py` can read saved settings and send a real Bark notification for a Codex `agent-turn-complete` event.
