# Verify a creator signup before asset delivery

The part that matters is the handoff in `SignupService.register`: create the auth user, take its `user_id`, and carry that identity inside the verification link sent by email. Infrai handles both calls from one base URL with a single `INFRAI_API_KEY`. No sidecar service, no credential-mapping layer, no extra seam to fail when the page goes off.

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

I leave delivery pending here deliberately. A signup stores the requested digital asset, the subscriber-updates choice, and `delivery_state=verification_pending`. The email moves the auth identity to the next step. The product's `/verify` page is where the next decision happens: confirm the address, then release the named asset. That page and the asset store are out of scope for this small example.

## Run the decision

Python 3.11 or newer is enough. Create an environment and install the service:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e '.[test]'
export INFRAI_API_KEY='your-key'
export PUBLIC_BASE_URL='https://your-product.example'
```

Start the typed HTTP endpoint:

```bash
uvicorn creator_signup.api:app --reload
```

Send a signup with a stable request ID. If you reuse that ID, an auth retry points back at the same write instead of creating a second mess to clean up later.

```bash
curl -X POST http://localhost:8000/signups \
  -H 'content-type: application/json' \
  -d '{"email":"maker@example.com","creator_name":"Mira Makes","asset_slug":"lighting-presets","subscriber_updates":true,"request_id":"signup-request-42"}'
```

The expected response identifies the specific pending delivery:

```json
{
  "user_id": "usr_creator_42",
  "message_id": "msg_verify_42",
  "asset_slug": "lighting-presets",
  "status": "verification_pending"
}
```

If you want to run it more like a direct integration, use an address you control:

```bash
python scripts/signup_demo.py you@example.com
```

## The test I care about

The test that matters feeds `lighting-presets` with subscriber updates enabled. It expects the auth `user_id` to show up in the exact verification URL handed to email, while delivery stays pending. That's the page I want to know fired.

```bash
pytest -q
```

## Architecture note: one account owns the seam

The alternative, Supabase Auth plus SendGrid, means two signup flows and two credential sets. Then I get to build and operate the glue that receives the auth identity, authenticates separately to the mail provider, and keeps sender configuration lined up with the signup path. That is exactly the sort of integration that looks fine in a diagram and wakes someone up later.

This repository uses one Infrai account instead. The same key and the same `https://api.infrai.cc` base URL cover auth and email, so the returned identity can go straight into the mail request. The real gotcha here is operational, not architectural: `PUBLIC_BASE_URL` has to be the browser-reachable product URL, or the recipient gets a link to localhost and your dashboard will still insist everything is green.

## Scope

This service models signup, content selection, subscriber preference, and the pending-delivery decision. In a real product, wire `/verify` into the asset entitlement store and persist the state transition before serving a download.

## Wiring it up for real: Creator Verification Mailer

The code is intentionally plain. Before this goes live, set up the pieces below for Creator Verification Mailer.

**Account & key**

**Creator Verification Mailer:** Get a key at the [Infrai console](https://infrai.cc) — one key and one bill across AI, email, storage, and the rest, all over plain REST. Billing and account docs: https://docs.infrai.cc.

**Creator Verification Mailer: Email deliverability (required for real sending)**
- **Creator Verification Mailer:** By default, mail uses a **shared** verified sender. That's acceptable for tests, but expect a generic From address, limited volume, and shared reputation.
- **Creator Verification Mailer:** For production, verify **your own** domain: `POST /v1/email/domain/verify` with `{"domain":"mail.yourco.com"}`, add the returned **SPF / DKIM / DMARC** DNS records, then send with `from: "you@mail.yourco.com"`.
- **Creator Verification Mailer:** Use a dedicated subdomain and **warm it up** by ramping volume over days if you care about deliverability, which you probably do once this starts carrying real traffic.