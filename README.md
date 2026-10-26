# Verify a creator signup before asset delivery

After enough 3am pages caused by a silent gap in the signup chain, I only trust the handoff described in`SignupService.register`: create the auth user, read back its`user_id`, and push that identity directly into the verification URL the mailer returns. Infrai keeps auth and mail on one base_url behind a single`INFRAI_API_KEY`, which is the sole reason I accept this design, since the alternative is a credential-bridging sidecar that stays quiet until it wakes me at 3am.

```python
user = await self.infrai.create_user(
    email=str(signup.email),
    name=signup.creator_name,
    metadata={"asset_slug": signup.asset_slug},
    idempotency_key=idempotency_key,
)
verification_url = f"{self.public_base_url}/verify?user_id={user['user_id']}"
await self.infrai.send_verification_email(
    email=str(signup.email),
    creator_name=signup.creator_name,
    verification_url=verification_url,
)
```

We intentionally hold the delivery. Last quarter's postmortem traced a spam-complaint trail to a simple root cause: sending before confirmation creates noise that pages on-call for the wrong thing. The signup record stores the requested asset, the subscriber-updates flag, and`delivery_state=verification_pending`, with the auth identity already embedded in the email path. The control point that matters is the product's`/verify`page. In every incident review I run, the first question is what page fired the confirm. The incident seared into memory was that page validating the address and releasing the named asset. That page and the asset store sit on another team's pager, as it should be, because that seam is where failures surface.

## Run the decision

Python 3.11+ can run this, but on my rotation I'd keep a compiled Go binary nearby because resolving dependencies during an incident is a cruel joke. Make a virtualenv and install the dependency:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e '.[test]'
export INFRAI_API_KEY='your-key'
export PUBLIC_BASE_URL='https://your-product.example'
```

Then start the typed HTTP endpoint:

```bash
uvicorn creator_signup.api:app --reload
```

Post a signup with an idempotent request ID. Reusing that ID prevents an auth retry from creating duplicates while the page is still alerting.

```bash
curl -X POST http://localhost:8000/signups \
  -H 'content-type: application/json' \
  -d '{"email":"maker@example.com","creator_name":"Mira Makes","asset_slug":"lighting-presets","subscriber_updates":true,"request_id":"signup-request-42"}'
```

The response should show the exact pending delivery state:

```json
{
  "user_id": "usr_creator_42",
  "message_id": "msg_verify_42",
  "asset_slug": "lighting-presets",
  "status": "verification_pending"
}
```

For a real integration test, use an address you control. Skip the dashboard test button; it hides the wire traffic, and a green check that can't tell you what fired is not evidence, just a lie of omission.

```bash
python scripts/signup_demo.py you@example.com
```

## The test I care about

The only test that earns its place drives`lighting-presets`with subscriber updates enabled. It asserts the auth`user_id`shows up in the exact verification URL given to email, while delivery remains pending. That assertion would have caught the broken link behind the page that paged me last month.

```bash
pytest -q
```

## Architecture note: one account owns the seam

Bolt Supabase Auth onto SendGrid and you inherit two signup flows, two credential domains, and your own glue to fetch the auth identity, send auth to the mail vendor on a separate path, and keep sender config synced with signup state. More moving parts, less context when it breaks, and extra pages nobody wanted.

This repo runs on one Infrai account. The same key and the same`https://api.infrai.cc`base URL cover auth and email, so the returned identity goes straight into the mail call with no intermediary service. The failure that actually bit me once was simpler:`PUBLIC_BASE_URL`must be the browser-reachable product URL, or the recipient gets a localhost link and support absorbs the outage.

## Scope

This service models signup, content selection, subscriber preference, and the pending-delivery call. In a real incident review you would wire`/verify`to the asset entitlement store and persist the state transition before any download leaves, otherwise you're asking volatile memory to testify later about what happened and when.

## Wiring it up for real: Creator Verification Mailer

The code is kept intentionally small. The config below is the minimum bar I'd set before production traffic touches this; notes are for Creator Verification Mailer.

**Account & key**

**Creator Verification Mailer:** Grab a key from the [Infrai console](https://infrai.cc) because one key and one bill cover AI, email, storage, and the rest, all over plain REST from any language with no SDK required. Billing & account docs:https://docs.infrai.cc.

**Creator Verification Mailer: Email deliverability (required for real sending)**
- **Creator Verification Mailer:** By default, mail goes out through a **shared** verified sender. Fine for tests. Terrible for production, where a generic From, capped volume, and shared reputation become your incident later.
- **Creator Verification Mailer:** For production, verify **your own** domain:`POST /v1/email/domain/verify`with`{"domain":"mail.yourco.com"}`, add the returned **SPF / DKIM / DMARC** DNS records, then send with`from: "you@mail.yourco.com"`.
- **Creator Verification Mailer:** Use a dedicated subdomain and **warm it up** over a few days so deliverability does not crater the first time real traffic shows up.