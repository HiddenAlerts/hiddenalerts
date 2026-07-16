import { NextResponse } from 'next/server';

const MAILERLITE_API = 'https://connect.mailerlite.com/api/subscribers';

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

type NewsletterBody = {
  email?: unknown;
};

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
  if (!token) {
    console.error('[newsletter] Missing MAILERLITE_API_TOKEN');
    return NextResponse.json(
      { error: 'Newsletter signup is temporarily unavailable.' },
      { status: 503 },
    );
  }

  try {
    const res = await fetch(MAILERLITE_API, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Accept: 'application/json',
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify({ email }),
    });

    // 201 created, 200 already exists / updated
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
