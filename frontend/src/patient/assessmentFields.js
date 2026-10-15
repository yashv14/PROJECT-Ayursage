// Exact structural contract from backend/app/api/assessment_validation.py and V17.
export const categoricalInputs = [
  'Disease', 'Symptom Severity', 'Nadi Reading', 'Constitution/Prakriti',
  'Stress Levels', 'Sleep Patterns', 'Age Group', 'Physical Activity Levels',
];
export const numericInputs = ['BP Systolic', 'BP Diastolic', 'Pulse Rate', 'Weight (kg)'];
export const inputFeatures = [...categoricalInputs, ...numericInputs];
export const outputTargets = [
  'Herbal Therapy Strategy', 'Lifestyle Recommendations',
  'Therapeutic Yoga Module', 'Follow-up Recommendation',
];
export const emptyInputs = () => Object.fromEntries(inputFeatures.map(name => [name, '']));

export function validText(value, maximum, nonblank = false) {
  return typeof value === 'string' && [...value].length <= maximum && !value.includes('\0')
    && (!nonblank || !!value.trim())
    && ![...value].some(char => char.length === 1 && /[\uD800-\uDFFF]/.test(char));
}

export function prepareAssessment(values, notes = '', predict = false) {
  const errors = {};
  const inputs = {};
  for (const name of categoricalInputs) {
    if (!validText(values[name], 256, true)) errors[name] = 'Enter nonblank text, up to 256 characters, without invalid characters.';
    else inputs[name] = values[name]; // Preserve supplied text, including whitespace.
  }
  for (const name of numericInputs) {
    const raw = values[name];
    // Empty input must never become Number('') === 0.
    const text = typeof raw === 'string' ? raw.trim() : '';
    if (!text || !/^[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:e[+-]?\d+)?$/i.test(text) || !Number.isFinite(Number(text))) {
      errors[name] = 'Enter a finite number. This field is required.';
    } else inputs[name] = Number(text);
  }
  if (!validText(notes, 4096)) errors.notes = 'Use up to 4096 characters without invalid characters.';
  if (typeof predict !== 'boolean') errors.form = 'Choose whether to request a prediction.';
  const payload = { inputs, ...(notes !== '' ? { notes } : {}), predict };
  if (!Object.keys(errors).length && new TextEncoder().encode(JSON.stringify(payload)).length > 16384) {
    errors.form = 'The assessment exceeds the API request limit of 16 KiB. Shorten the text or notes.';
  }
  return { errors, payload: Object.keys(errors).length ? null : payload };
}
