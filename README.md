# SAP Community Daily Digest

Every morning at 7:00 IST this robot:

1. Collects **every** new blog post, question, discussion and news item from SAP Community. It checks every 3 hours, so nothing slips past on busy days.
2. Has Claude **screen every item** and sort it by area and importance.
3. Has Claude **read the most important ones in full**. By default that's up to 30 a day.
4. Has Claude write a **deep daily report**: top stories, releases, deep dives, what developers are struggling with, and ready-to-post drafts for your community.
5. Publishes the report as a web page and **sends the highlights plus the link to your WhatsApp**.

Only official services are involved:

- **SAP Community's own feeds:** the source of all content.
- **Claude Code on your Claude Pro subscription:** does the reading and writing, with no separate API bill.
- **Meta's WhatsApp Cloud API:** delivers the message.
- **GitHub:** runs the schedule and hosts the report.

Report archive: https://ganeshdudi.github.io/sap-daily-digest

---

## Part A: Connect your Claude subscription (10 minutes, once)

1. On your laptop, open **PowerShell**. Press the Windows key, type `PowerShell`, and press Enter.
2. Install Claude Code by pasting this and pressing Enter:

```
irm https://claude.ai/install.ps1 | iex
```

3. **Close PowerShell and open it again**, so it picks up the new `claude` command.
4. Run this command:

```
claude setup-token
```

5. A browser opens. Log in with your Claude account (the one with Pro) and approve.
6. PowerShell prints a long token starting with `sk-ant-oat`. **Copy it right away.** It is shown only once. Don't paste it into any chat; it goes straight into GitHub as a secret.
7. In GitHub, go to **Settings**, then **Secrets and variables**, then **Actions**, then **New repository secret**:
   - **Name:** `CLAUDE_CODE_OAUTH_TOKEN`
   - **Secret:** paste the token.
8. Open the **Actions** tab and run **Test Claude connection**. The log should end with "Claude is connected to the SAP digest."

**About your usage.** The daily run uses part of your normal Pro usage allowance, the same one you use in chat. It runs at 7 AM and is kept light (about 11 requests a day), so most of it has reset by the time your workday starts. If your limit is ever reached mid-run, you still get a report of the screened items, with a note explaining why the deep analysis was skipped.

---

## Part B: WhatsApp, official Meta API (20 minutes)

Menu names on Meta's site change occasionally. If a label differs slightly, look for the closest match.

### B1. Create the app

1. Go to **developers.facebook.com**, log in with Facebook, and register as a developer if asked.
2. Click **My Apps**, then **Create App**.
3. Choose the WhatsApp use case, or the **Business** type if asked. Give it a name like `SAP Digest`.
4. Create or select a business portfolio when prompted.

### B2. Get the test number and add your phone

1. In the app, open **WhatsApp**, then **API Setup**.
2. Meta gives you a free **test phone number**. Copy its **Phone number ID**, which is a long number.
3. In the **To** field, click **Manage phone number list** and add **your own WhatsApp number**. Confirm it with the code Meta sends you.
4. Click **Send message**. You should receive Meta's "Hello World" message on WhatsApp. Reply "hi" to it once.

### B3. Create the digest template

Meta only lets businesses start a conversation using pre-approved message templates. You need to create one.

1. Open **WhatsApp Manager**. It's linked from API Setup, or at business.facebook.com. Go to **Message templates** and click **Create template**.
2. Fill in these settings:
   - **Category:** Utility
   - **Name:** `sap_daily_digest` (exactly this)
   - **Language:** English
3. Use this **Body** text:

```
Your SAP Community digest for {{1}} is ready.

Top stories: {{2}}

Read the full report here: {{3}}

This is your automated daily briefing.
```

4. When asked for sample values, use these:
   - `{{1}}`: `Friday, 25 September 2026`
   - `{{2}}`: `New RAP draft features in ABAP Platform | ADT release notes | CDS access control questions trending`
   - `{{3}}`: `https://ganeshdudi.github.io/sap-daily-digest/reports/2026-09-25.html`
5. Submit the template. Approval usually takes minutes to a few hours. If Meta files it under **Marketing** instead, that's fine, because it still works.
6. If you picked a specific English variant such as "English (US)", change `template_language` in `config.yaml` to `en_US`.

### B4. Create a permanent access token

The token shown on API Setup expires in 24 hours, so you need a permanent one.

1. Go to **business.facebook.com** and open **Settings**. Under **Users**, choose **System users**, then **Add**. Name it `digest-bot` and give it the **Admin** role.
2. Click **Assign assets** and grant **full control** of your app and your WhatsApp account.
3. Click **Generate token**:
   - Select your app.
   - Set **Expiry** to **Never**.
   - Tick `whatsapp_business_messaging` and `whatsapp_business_management`.
4. Copy the token and keep it safe.

### B5. Save the WhatsApp secrets

In GitHub, go to **Settings**, then **Secrets and variables**, then **Actions**, then **New repository secret**. Add these three:

- `WA_TOKEN`: the permanent token from step B4.
- `WA_PHONE_NUMBER_ID`: the Phone number ID from step B2.
- `WA_TO`: your WhatsApp number with the country code and no plus sign, for example `919876543210`.

---

## Part C: Test everything

Open the **Actions** tab.

1. Run **Test WhatsApp connection**. You should get Meta's Hello World message on WhatsApp.
2. Run **Collect SAP Community posts**. It should finish green.
3. Run **Daily SAP digest**. It takes about 5–15 minutes. Your WhatsApp digest then arrives with the report link.

From tomorrow, everything runs by itself.

---

## Using and adjusting it

**Change the delivery time.** Edit `.github/workflows/digest.yml`. The cron time is in UTC, and IST is UTC + 5:30. For example, `30 1 * * *` is 07:00 IST and `0 3 * * *` is 08:30 IST.

**Deep-read every SAP area, not just technical ones.** In `config.yaml`, set `mode: everything`. Every item is already listed in the report either way. This setting only controls which items get the full read.

**Read more or fewer posts in full.** Change `max_deep_reads` in `config.yaml`. More posts means more of your Pro usage each morning.

**Adjust your interests.** Edit `focus_areas` and `audience` in `config.yaml`.

**See how much it used.** The end of each run's log on GitHub (Actions) shows how many requests and tokens the run used. It is covered by your subscription, not billed separately.

**Scheduled runs are late.** GitHub sometimes starts scheduled jobs 5–30 minutes late during busy periods. This is normal.

---

## SAP job market agent (jobs.py)

Besides company careers sites, `jobs.py` pulls jobs from Adzuna's India index and your job-alert emails. Every company careers site is added to `config.yaml` only after two checks: a live "SAP ABAP" search that actually returns jobs, and its `robots.txt` / terms of use, to confirm automated access is allowed.

**Currently included:**

- **SAP** (`jobs.sap.com`) — SuccessFactors RSS search. `robots.txt` allows all paths, and the search returns ABAP roles.

**Tried and skipped:**

| Company | Platform | Why it was skipped |
| --- | --- | --- |
| Wipro, HCLTech, EY, Deloitte India, NTT DATA | SuccessFactors | Each returned jobs for an "SAP ABAP" search, but their `robots.txt` disallows `/services/`, which is exactly the RSS path (`/services/rss/job/`) this agent would need to call. |
| Accenture, PwC, Shell, ZEISS, Mitel | Workday | Returned jobs (or, for 3M, Momentive and Dentsu, returned none at all), but Workday's own terms of service prohibit "data mining, robots or similar data gathering or extraction methods" against any `myworkdayjobs.com` site, regardless of what an individual tenant's `robots.txt` allows. |
| 3M, Momentive, Dentsu | Workday | A live "SAP ABAP" search returned zero jobs, so there is nothing to add even before the terms-of-service issue above. |
| Oracle (KPMG India) | Oracle Recruiting Cloud | The search API works and returns ABAP roles, but KPMG's applicant-tracking terms of use explicitly prohibit "data mining, robots or similar data gathering or extraction methods" on their careers site. |
| IBM | — | IBM's public careers page (`ibm.com/careers/search`) is a JavaScript app with no documented data API, and its underlying jobs site (`careers.ibm.com`) returns an empty bot-check response to plain HTTP requests, so no automated search could be run at all. |

Because none of the candidates above cleared both checks, `job_sources.py` keeps only the `successfactors` and `workday` source types it already had — no new source type was needed for this round.

---

## If something goes wrong

Open **Actions**, click the red run, and read the last lines of the log.

- **"Missing secret CLAUDE_CODE_OAUTH_TOKEN":** the secret name is misspelled or missing. Redo Part A, step 7.
- **Claude login or 401 errors:** the token has expired or was revoked. Run `claude setup-token` again and replace the secret.
- **"usage limit reached":** your Pro allowance ran out during the run. Lower `max_deep_reads` in `config.yaml`, or move the run to an earlier time.
- **Feeds fail with 403 or 429:** SAP Community is blocking GitHub's servers. Share the log and the fetch method can be adjusted.
- **WhatsApp error `132001`:** the template isn't approved yet, or the name or language code doesn't match `config.yaml`.
- **WhatsApp error `131030`:** your number isn't in the test recipient list. Redo step B2.
- **WhatsApp error `190`:** the WhatsApp token expired. You probably used the 24-hour token; redo step B4.
- **The report link shows 404:** GitHub Pages isn't on, or the page needs a minute more to go live.
