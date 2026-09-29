// Keep this list aligned with COMMON_PASSWORDS in the API. The server decides.
const COMMON_PASSWORDS = new Set([
  "123456789012",
  "1234567890123",
  "1q2w3e4r5t6y",
  "1qaz2wsx3edc",
  "abc123456789",
  "access123456",
  "admin1234567",
  "ashley123456",
  "asdfghjkl123",
  "bailey123456",
  "baseball1234",
  "batman123456",
  "changeme1234",
  "computer1234",
  "dragon123456",
  "football1234",
  "ghostline123",
  "iloveyou1234",
  "internet1234",
  "letmein12345",
  "master123456",
  "michael12345",
  "monkey123456",
  "passw0rd1234",
  "password1234",
  "password12345",
  "passwordpassword",
  "princess1234",
  "qwerty123456",
  "qwertyuiop12",
  "qwertyuiopas",
  "shadow123456",
  "starwars1234",
  "sunshine1234",
  "superman1234",
  "trustno11234",
  "welcome12345",
  "whatever1234",
  "zxcvbnm12345",
]);

export function passwordStrength(password) {
  if (!password) {
    return { label: "At least 12 characters", score: 0 };
  }
  if (password.length < 12) {
    return { label: "Use at least 12 characters", score: 1 };
  }
  if (COMMON_PASSWORDS.has(password.toLowerCase())) {
    return { label: "Too common", score: 1 };
  }
  let classes = 0;
  if (/[a-z]/.test(password)) classes += 1;
  if (/[A-Z]/.test(password)) classes += 1;
  if (/[0-9]/.test(password)) classes += 1;
  if (/[^A-Za-z0-9]/.test(password)) classes += 1;
  if (password.length >= 16 || classes >= 3) {
    return { label: "Strong", score: 3 };
  }
  if (classes >= 2) {
    return { label: "Fair", score: 2 };
  }
  return { label: "Weak", score: 1 };
}

export function passwordIsAcceptable(password) {
  return password.length >= 12 && !COMMON_PASSWORDS.has(password.toLowerCase());
}
