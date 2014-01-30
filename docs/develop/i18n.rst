Fuel UI Internationalization Guidelines
=======================================
Fuel UI internationalization is done using `i18next <http://i18next.com/>`_
library. Please read `i18next documentation
<http://i18next.com/pages/doc_features.html>`_ first.

All translations are stored in nailgun/static/i18n/translation.json

If you want to add new strings to the translations file, follow these rules:

#. Use words describing placement of strings like "button", "title", "summary",
   "description", "label" and place them at the end of the key
   (like "apply_button", "cluster_description", etc.). One-word strings may
   look better without any of these suffixes.
#. Do NOT use shortcuts ("bt" instead of "button", "descr" instead of
   "description", etc.)
#. Nest keys if it makes sense, for example, if there are a few values
   for statuses, etc.
#. If some keys are used in a few places (for example, in utils), move them to
   "common.*" namespace.
#. Use defaultValue ONLY with dynamically generated keys.

Validating translations
=========================================
To search for absent and unnecessary translation keys you can perform the following steps:

#. Open terminal and cd to fuel-web/nailgun directory.
#. Run "grunt i18n:validate" to start the validation.
   If there are any mismatches, you'll see the list of mismatching keys.

Grunt task "i18n:validate" has one optional argument - a comma-separated list of
languages to compare with base English en-US translations. Run
"grunt i18n:validate:zh-CN" to perform comparison only between English and
Chinese keys. You can also run "grunt i18n:validate:zh-CN,ru-RU" to perform
comparison between English-Chinese and English-Russian keys.
