# SAP Community Daily Digest

Every morning at 7:00 IST this robot:

1. Collects **every** new blog post, question, discussion and news item from SAP Community. It checks every 3 hours, so nothing slips past on busy days.
2. Has Claude **screen every item** and sort it by area and importance.
3. Has Claude **read the most important ones in full**. By default that's up to 60 a day.
4. Has Claude write a **deep daily report**: top stories, releases, deep dives, what developers are struggling with, and ready-to-post drafts for your community.
5. Publishes the report as a web page and **sends the highlights plus the link to your WhatsApp**.

Only official services are involved:

- **SAP Community's own feeds:** the source of all content.
- **Anthropic's Claude API:** does the reading and writing.
- **Meta's WhatsApp Cloud API:** delivers the message.
- **GitHub:** runs the schedule and hosts the report.

Report archive: https://ganeshdudi.github.io/sap-daily-digest

---

## Part A: Claude API key (5 minutes)

1. Go to **console.anthropic.com** and sign up.
2. Open **Billing** and add credit. $10 is plenty to start.
3. Optional but recommended: open **Limits** and set a monthly spend limit, such as $30.
4. Open **API Keys**, click **Create Key**, and copy it somewhere safe. It is only shown once.

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

---

## Part C: GitHub settings

### C1. Add your secrets

Go to **Settings**, then **Secrets and variables**, then **Actions**, then **New repository secret**. Add these four:

- `ANTHROPIC_API_KEY`: your Claude key from Part A.
- `WA_TOKEN`: the permanent token from step B4.
- `WA_PHONE_NUMBER_ID`: the Phone number ID from step B2.
- `WA_TO`: your WhatsApp number with the country code and no plus sign, for example `919876543210`.

### C2. Allow the robot to save reports

1. Go to **Settings**, then **Actions**, then **General**.
2. Under **Workflow permissions**, choose **Read and write permissions** and click **Save**.

### C3. Turn on the report website

1. Go to **Settings**, then **Pages**.
2. Under **Source**, choose **Deploy from a branch**.
3. Set **Branch** to `main` and the folder to `/docs`, then click **Save**.

### C4. Test everything

Open the **Actions** tab. Enable workflows if GitHub asks.

1. Run **Test WhatsApp connection**. You should get Meta's Hello World message on WhatsApp.
2. Run **Collect SAP Community posts**. It should finish green.
3. Run **Daily SAP digest**. It takes about 5–15 minutes. Your WhatsApp digest then arrives with the report link.

From tomorrow, everything runs by itself.

---

## Using and adjusting it

**Change the delivery time.** Edit `.github/workflows/digest.yml`. The cron time is in UTC, and IST is UTC + 5:30. For example, `30 1 * * *` is 07:00 IST and `0 3 * * *` is 08:30 IST.

**Deep-read every SAP area, not just technical ones.** In `config.yaml`, set `mode: everything`. Every item is already listed in the report either way. This setting only controls which items get the full read.

**Read more or fewer posts in full.** Change `max_deep_reads` in `config.yaml`.

**Adjust your interests.** Edit `focus_areas` and `audience` in `config.yaml`.

**Check costs.** Every run prints the exact token usage at the end of its log on GitHub, under Actions. Expect roughly $10–30 a month, depending on how busy SAP Community is. Your spend limit from Part A caps it.

**Scheduled runs are late.** GitHub sometimes starts scheduled jobs 5–30 minutes late during busy periods. This is normal.

---

## If something goes wrong

Open **Actions**, click the red run, and read the last lines of the log.

- **Feeds fail with 403 or 429:** SAP Community is blocking GitHub's servers. Share the log and the fetch method can be adjusted.
- **WhatsApp error `132001`:** the template isn't approved yet, or the name or language code doesn't match `config.yaml`.
- **WhatsApp error `131030`:** your number isn't in the test recipient list. Redo step B2.
- **WhatsApp error `190`:** the token expired. You probably used the 24-hour token; redo step B4.
- **Claude error `401`:** the API key is wrong. Error `400` mentioning credit means you need to add billing credit.
- **The report link shows 404:** GitHub Pages isn't on (step C3), or the page needs a minute more to go live.
