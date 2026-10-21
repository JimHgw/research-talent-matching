import simplifiedChinese from './zh-CN.js';
import traditionalChinese from './zh-TW.js';
import spanish from './es.js';
import french from './fr.js';
import german from './de.js';
import portuguese from './pt.js';
import japanese from './ja.js';
import korean from './ko.js';
import arabic from './ar.js';
import hindi from './hi.js';
import russian from './ru.js';

// Native names keep the selector usable after an accidental language switch.
// Each dictionary remains independently editable; English source messages are the fallback.
export const languageCatalog = {
  en: { label: 'English', direction: 'ltr', messages: {} },
  'zh-CN': { label: '简体中文', direction: 'ltr', messages: simplifiedChinese },
  'zh-TW': { label: '繁體中文', direction: 'ltr', messages: traditionalChinese },
  es: { label: 'Español', direction: 'ltr', messages: spanish },
  fr: { label: 'Français', direction: 'ltr', messages: french },
  de: { label: 'Deutsch', direction: 'ltr', messages: german },
  pt: { label: 'Português', direction: 'ltr', messages: portuguese },
  ja: { label: '日本語', direction: 'ltr', messages: japanese },
  ko: { label: '한국어', direction: 'ltr', messages: korean },
  ar: { label: 'العربية', direction: 'rtl', messages: arabic },
  hi: { label: 'हिन्दी', direction: 'ltr', messages: hindi },
  ru: { label: 'Русский', direction: 'ltr', messages: russian },
};

export const supportsLanguage = (value) => Object.hasOwn(languageCatalog, value);
export const languageDefinition = (value) =>
  languageCatalog[supportsLanguage(value) ? value : 'en'];
