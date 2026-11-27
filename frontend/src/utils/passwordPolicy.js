// Client-side mirror of the server's password policy (backend/app/services/passwords.py), for
// a live checklist. The server is the authority: it also checks a common-password list and
// that the password doesn't contain the user's name or email.

export const PASSWORD_MIN = 10;

const CLASSES = [/[a-z]/, /[A-Z]/, /\d/, /[^A-Za-z0-9]/];

export function passwordChecks(password) {
  const varieties = CLASSES.filter((re) => re.test(password)).length;
  return [
    { id: 'length', label: `At least ${PASSWORD_MIN} characters`, ok: password.length >= PASSWORD_MIN },
    { id: 'variety', label: 'Three of: lowercase, uppercase, digit, symbol', ok: varieties >= 3 },
  ];
}

export function meetsBasicPolicy(password) {
  return passwordChecks(password).every((check) => check.ok);
}

const SETS = ['abcdefghijkmnopqrstuvwxyz', 'ABCDEFGHJKLMNPQRSTUVWXYZ', '23456789', '!@#$%^&*-_+=?'];

/** A random 16-character password with every character class (no look-alikes such as l/1/O/0). */
export function generatePassword(length = 16) {
  const all = SETS.join('');
  const random = (max) => {
    const buf = new Uint32Array(1);
    crypto.getRandomValues(buf);
    return buf[0] % max;
  };
  const chars = SETS.map((set) => set[random(set.length)]);
  while (chars.length < length) chars.push(all[random(all.length)]);
  for (let i = chars.length - 1; i > 0; i -= 1) {
    const j = random(i + 1);
    [chars[i], chars[j]] = [chars[j], chars[i]];
  }
  return chars.join('');
}
