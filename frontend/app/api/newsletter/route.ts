import { NextResponse } from 'next/server';

const MAILERLITE_SUBSCRIBERS_URL =
  'https://connect.mailerlite.com/api/subscribers';

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

type NewsletterBody = {
  email?: unknown;
};

/**
 * Newsletter signup → MailerLite create/upsert into the configured group.
 *
 * Env (server-only, set in Vercel Production + Preview):
 * - MAILERLITE_API_TOKEN
 * - MAILERLITE_GROUP_ID  (HiddenAlerts Intelligence group)
 *
 * Success is returned only after MailerLite accepts the subscriber.
 */
export async function POST(request: Request) {
  let body: NewsletterBody;
  try {
    body = (await request.json()) as NewsletterBody;
  } catch {
    return NextResponse.json(
      { error: 'Invalid request body.' },
      { status: 400 },
    );
  }

  const email =
    typeof body.email === 'string' ? body.email.trim().toLowerCase() : '';

  if (!email || !EMAIL_RE.test(email) || email.length > 254) {
    return NextResponse.json(
      { error: 'Please enter a valid email address.' },
      { status: 400 },
    );
  }

  const token = process.env.MAILERLITE_API_TOKEN?.trim();
  const groupId = process.env.MAILERLITE_GROUP_ID?.trim();

  if (!token || !groupId) {
    console.error(
      '[newsletter] Missing MAILERLITE_API_TOKEN or MAILERLITE_GROUP_ID',
    );
    return NextResponse.json(
      { error: 'Newsletter signup is temporarily unavailable.' },
      { status: 503 },
    );
  }

  try {
    const res = await fetch(MAILERLITE_SUBSCRIBERS_URL, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Accept: 'application/json',
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify({
        email,
        groups: [groupId],
      }),
    });

    // 201 created, 200 already exists / updated (group assignment included)
    if (res.ok) {
      return NextResponse.json({ ok: true });
    }

    const detail = await res.text().catch(() => '');
    console.error('[newsletter] MailerLite error', res.status, detail);
    return NextResponse.json(
      { error: 'Unable to subscribe right now. Please try again.' },
      { status: 502 },
    );
  } catch (cause) {
    console.error('[newsletter] Network error', cause);
    return NextResponse.json(
      { error: 'Unable to subscribe right now. Please try again.' },
      { status: 502 },
    );
  }
}
