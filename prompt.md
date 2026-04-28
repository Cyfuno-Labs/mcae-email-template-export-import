# Marketing Cloud Account Engagement (MCAE / Pardot) Mass Email Template Updater
This python project can be used for 2 key purposes.

1. Extract EmailTemplate information from MCAE
2. Update EmailTemplate information to MCAE

It will be a CLI interface, designed to be run by a technical marketer (not a developer).

On the first run, it should look to see if a .env file is present. if it is not, it should copy the .env-sample and ask for each value to update the file, then exit.
On future runs, it should just run as intended.

## Extract EmailTemplate Information
We will need to use the Email Template API to retrieve all email templates. When the extract has completed, we should have a spreadsheet in the working directory that lists:
- Email Template Id
- Name
- Subject
- Campaign Name
- Ready To Update (used on import)
- Text Message File Path (relative to working directory, should have reference to the updated file)
- HTML Message File Path (relative to working directory, should have reference to the updated file)

After the extract is complete, print some stats to the screen. Time elapsed, number of email templates downloaded, number of API calls made.

## Import EmailTemplate Information
The goal here is to simply provide updated `htmlMessage` and `textMessage` values to the Pardot API.  These values will have lots of text, sent in a JSON payload so we might need to be careful with escaping certain values. Don't try to validate either of the 2 files, as MCAE has its own merge variable etc that we don't want to mess with.

The script should make sure that the spreadsheet is present, and for any email template rows that have "Ready to Update" set to Yes/True or whatever, the script should make sure the files referenced at the 2 File Paths can be found.

When using the Update Email Template API, the script should first download a fresh copy of the email template's htmlMessage and textMessage as a backup, then update the template, then update the spreadsheet to indicate success / failure message. On a failure, the script should abort.

After the import is done (either success or failure), print some stats to the screen. Time elapsed, number of email templates updated, number of API calls made.

## Technical Specs

### Directory Structure
/[working directory]/[campaign name]/[email name]/

Within each directory, there will be multiple files.
- content-original.html: populated from the `htmlMessage` property
- content-updated.html: populated from the `htmlMessage` property (file to be replaced by the user for upload purposes)
- content-original.txt: populated from the `textMessage` property
- content-updated.txt: populated from the `textMessage` property (file to be replaced by the user for upload purposes)

### Environment Variables
- Salesforce MyDomain
- Salesforce External Client App Id
- Salesforce External Client App Secret
- Pardot Business Unit Id
- Pardot Org Type: production, sandbox, demo org (which has Production salesforce urls but pi.demo.pardot.com URL for Pardot API requests like a sandbox)

### Command Line Arguments - Extract
We want to give the user the ability to filter which email templates are extracted.
- Name - This argument value will be used to look at the email template names, in a "contains" or "like" manner. The API doesn't support filtering like this, so we have to do it ourselves. Should prompt the user "We found X Email Templates, proceed?" before doing the extract
- CampaignName - This argument will look at the `campaign.name` attribute of the Email Template, in a "contains" manner. Should prompt the user "We found X Campaigns with Y Email Templates, proceed?" before doing the extract.
- Tags - This argument (accepting a CSV set of tags) will have to look up the Tag (using Tag Query API) for each name, then find the TaggedObjects to get a list of Email Template IDs. Should prompt the user "We found X Tags with Y Email Templates, proceed?" before doing the extract

References
- https://developer.salesforce.com/docs/marketing/pardot/guide/email-template-v5.html#email-template-query
- https://developer.salesforce.com/docs/marketing/pardot/guide/email-template-v5.html#email-template-update
- https://developer.salesforce.com/docs/marketing/pardot/guide/tag-v5.html#query
- https://developer.salesforce.com/docs/marketing/pardot/guide/tagged-object-v5.html#query

## Code Architecture
I want a /lib folder, and there should be a `pardot.py` file for building the `PardotClient` class. This PardotClient class should accept the access_token_response as an argument. This should act like a super simple rest client. Our query API calls should retrieve 1000 results and the client should automatically retrieve next pages. it should also handle network glitches and occaisional pardot issues by retrying a failed request one time before throwing an error/exception.

I've got this code for getting the oauth token
```
# Small helper to make OAuth POSTs robust and provide actionable errors without leaking secrets
def retrieve_oauth_token(url: str, data: dict, timeout: int = 30) -> dict:
    resp = requests.post(url, data=data, timeout=timeout)
    content_type = resp.headers.get('Content-Type', '')
    if resp.status_code >= 400:
        # Truncate body to avoid flooding logs; do not include secrets (we only log response)
        body_preview = (resp.text or '')[:500]
        raise RuntimeError(
            f"OAuth token request failed: {resp.status_code} {resp.reason}; Content-Type: {content_type}; Body: {body_preview}"
        )
    try:
        return resp.json()
    except Exception:
        body_preview = (resp.text or '')[:500]
        raise RuntimeError(
            f"OAuth token response not JSON; Content-Type: {content_type}; Body: {body_preview}"
        )

# Salesforce credentials (robust handling)
access_token_response = retrieve_oauth_token(
    os.getenv('SF_URL') + '/services/oauth2/token', # this URL should come from environment
    data={
        'grant_type': 'client_credentials',
        'client_id': os.getenv('CLIENT_ID'),
        'client_secret': os.getenv('CLIENT_SECRET')
    }
)
```