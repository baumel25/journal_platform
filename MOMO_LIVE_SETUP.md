# MTN MoMo LIVE Setup — Rollout Guide

This guide is for the **journal manager** (the person who owns/controls the
journal and its MoMo account). It explains how to move the platform's online
payments from the free *sandbox* (test mode) to *live* mode, so readers get a
real payment prompt on their phone and the money arrives **directly in the
journal manager's MTN MoMo account**.

The platform code is already live-ready — no programming needed. This is a
business + configuration process with MTN.

---

## Who does what

| Task | Owner |
|---|---|
| Apply to MTN for the **live MoMo API (business)** account | Journal manager |
| Provide MTN's business/KYC documents | Journal manager |
| Confirm the receiving MoMo number is **678391473** | Journal manager |
| After approval, set the live keys in the server | Journal manager (or developer) |
| Swap the config from sandbox → live | One config change (below) |

---

## Progress log

- **2026-09-23 — Developer account ready (in the portal)**
  - Signed in at <https://momodeveloper.mtn.com> (account `christianyonta73@gmail.com`, created 2026-09-09).
  - Subscribed to the **Collections** product in the **sandbox** (subscription name `instructor-jcsa`).
    The sandbox **Primary key** / **Secondary key** live on <https://momodeveloper.mtn.com/profile>.
  - Provisioned the sandbox **API User + API Key** via the Sandbox User Provisioning API
    (`POST /v1_0/apiuser` then `POST /v1_0/apiuser/{id}/apikey` on `https://sandbox.momodeveloper.mtn.com`).
  - Local note with these sandbox values: `_momo_provision.txt` (never commit it, never put it in the repo).
- **Next: submit the Go-Live (production) application** — needs the manager's details + signed KYC docs (see A.1 below).

---

## Part A — The manager applies to MTN (this is the real step)

> ⚠️ Even when a developer acts on the manager's behalf, the application MUST
> be registered to the **journal's business** with collection number
> **678391473** — MTN pays into the registered merchant account, not the person
> who fills the form.

### A.0 — Info to collect from the journal manager (exactly what the wizard asks)

- [ ] **Business owner identity** (the manager): full name · National ID or
      Passport number · phone number · email address
- [ ] **Business name** exactly as registered + its **legal entity type**
      (sole proprietor / partnership / limited company / school…)
- [ ] A 1–2 line **description of the business** (the journal)
- [ ] Confirmation the collection MoMo number is: **678391473**
- [ ] The **signed KYC documents** (see A.1) — the manager must fill and sign them
- [ ] Confirmation the callback URL below is correct:
      `https://www.i-jcsa.com/articles/payment/callback/`

### A.1 — Apply for live/production access (the "Go-Live" wizard)

1. Sign in at **https://momodeveloper.mtn.com** and click **Go-Live**
   (top-left), or open **https://momodeveloper.mtn.com/golive** directly.
2. **Step 1 — Select Package**: choose country **Cameroon**, then tick the
   product set **Collections** → **Next**.
3. **Step 2 — About Your Business** (use the journal's / manager's real details):
   - *About Business Owner*: Full name · National ID / Passport number · Phone · Email
   - *About the Business*: Business name · legal-entity type (dropdown, e.g.
     SOLE PROPRIETOR, PARTNERSHIP, LIMITED COMPANY INCORPORATED IN Cameroon,
     SCHOOLS/EDUCATION INSTITUTIONS, MINISTRIES/PUBLIC SECTOR…) · a description
   - *KYC Contracting and File Management*: click **Download Application Forms**
     (this is the Cameroon pack `CMR_KYC_Documents.zip`, also copied into
     `momo_kyc/` in this project), have the manager **fill in and sign** the
     forms, then **upload them back as a single PDF**.
   - Tick the certification checkbox (truth + MTN Open API Terms and Conditions)
     and click **Submit**.
4. MTN reviews the application (typically days–weeks) and may call the listed
   contact to verify the business.
5. Once approved, MTN enables **production** credentials — then continue to Part B.

> MTN may contact you to verify the business. Have the manager's authorization
> and documents ready to share.

Once approved, MTN enables **live credentials** on your developer account:
- `MOMO_API_USER` (API user UUID)
- `MOMO_API_KEY` (API key)
- `MOMO_SUBSCRIPTION_KEY` (primary key)
- Confirm the **live base URL** (`https://momodeveloper.mtn.com`) and
  **target environment = live**.

> ⏱ MTN's approval can take days to weeks depending on their review queue.

> 📄 The Cameroon KYC pack (`CMR_KYC_Documents.zip`) contains:
> `API Services Contract 2025.pdf`, `KYC Form_MoMo.pdf`, `AML Questionnaire.pdf`,
> `Questionnaire Onboarding API - EN/FR.xlsx`,
> `ENGAGEMENT LETTER HIGH RISK ENTITIES.pdf`, `Lettre engagement sur honneur (ART).pdf`,
> `Information Security Schedule.pdf`. A downloaded copy is in `momo_kyc/` here.

---

## Part B — Once MTN approves (developer or manager does this)

On the server, edit the `.env` (or hosting environment variables):

```ini
MOMO_API_USER=<live API user>
MOMO_API_KEY=<live API key>
MOMO_SUBSCRIPTION_KEY=<live primary key>
MOMO_TARGET_ENVIRONMENT=live
MOMO_BASE_URL=https://momodeveloper.mtn.com
MOMO_CALLBACK_URL=https://www.i-jcsa.com/articles/payment/callback/
BASE_URL=https://www.i-jcsa.com
```

> The callback URL **must** be reachable over public HTTPS — MTN's servers
> will call it to confirm each payment. Deploy the latest code first, then
> set these values and restart the app.

---

## Part C — Verify with a real (tiny) payment

Run from the server (or locally with the live keys):

```bash
python manage.py test_momo 6XXXXXXXX
```

It sends a small request-to-pay to that MTN number. Approve it on the phone
and confirm the gateway reports `SUCCESSFUL`.

Then do a real checkout on the site:
1. Open a published article (no login) → **preview** only.
2. Click **Pay** → enter an MTN number → **approve the prompt on the phone**.
3. The article unlocks **only after** the phone approval is confirmed.

Money now lands in **678391473** (the manager's account).

---

## Important reminders

- **Nothing unlocks before payment is approved** — the site only grants access
  after MTN confirms a successful transaction (verified server-side).
- **Orange Money** is a separate process (Orange merchant account, not MTN).
- Keep the **sandbox** keys handy for testing; never mix the two environments.
- These are **secrets**: only the manager/developer should handle them, and
  they should live in `.env` / the hosting dashboard — never in emails or chats.
