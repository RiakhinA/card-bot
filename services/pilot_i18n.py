"""Small centralized localization source for the active Telegram Pilot."""

from __future__ import annotations


SUPPORTED_LANGUAGES = {"ru", "uk", "en"}
FALLBACK_LANGUAGE = "ru"


COPY = {
    "uk": {
        "back": "← Назад", "cancel": "✕ Скасувати", "cancel_application": "Скасувати заявку",
        "done": "Готово ✓", "continue": "Продовжити", "skip": "Пропустити",
        "not_selected": "не вибрано", "not_specified": "не вказано", "not_added": "не додано", "step": "Крок {current} із {total}", "current_section": "Поточний розділ", "core_section": "Основна інформація", "review_section": "Перевірка й надсилання",
        "start_intro": "<b>RIAKHIN CARD - цифрова візитка.</b>\n\nОдне посилання, де зібрана основна інформація про вас, контакти та потрібні способи зв’язку.\n\nСпочатку виберіть мову візитки.\nПотім виберіть розділи, які хочете додати.\n\nДля заповнення знадобляться ім’я, сфера роботи, опис і фото, логотип або варіант без зображення.",
        "interface_language": "<b>Мова спілкування в боті</b>",
        "price_intro": "<b>Вартість візитки</b>\n\nОдна мова: <b>1200 грн / $29</b>\nДві мови: <b>1700 грн / $39</b>\n\nСпочатку виберіть мову самої візитки. Це окремий вибір від мови спілкування в боті.",
        "card_language_count": "Скільки мов потрібно для візитки?\n\nДві мови підійдуть, якщо ви працюєте з аудиторією різними мовами або хочете надсилати одне посилання різним клієнтам.\n\nОдна мова: 1200 грн / $29\nДві мови: 1700 грн / $39",
        "one_language": "Одна мова", "two_languages": "Дві мови", "other_language": "Інша мова",
        "choose_card_language": "Виберіть мову візитки.", "choose_two_card_languages": "Виберіть дві мови для візитки. На сторінці з’явиться перемикач біля імені та фото.",
        "confirm_language": "Підтвердити мову ✓", "confirm_two_languages": "Підтвердити 2 мови ✓",
        "choose_language": "Виберіть мову", "choose_two_languages": "Виберіть 2 мови",
        "custom_language_prompt": "Напишіть потрібну мову. Наприклад: Polski, Deutsch або Español.",
        "custom_language_added": "Мову додано. Підтвердьте вибір або виберіть ще одну мову.",
        "select_exact_languages": "Виберіть, будь ласка, потрібну кількість мов.",
        "modules_title": "<b>Що буде у візитці?</b>\n\n<b>Основна інформація - обов’язково:</b> ім’я/бренд, сфера роботи, фото/логотип/без зображення та опис.\n\n<b>Додаткові розділи:</b> виберіть лише те, що хочете додати.",
        "social": "Соціальні мережі", "contacts": "Контакти", "projects": "Проєкти та посилання",
        "core_name": "Чудово. Почнімо з основної інформації.\n\nЯке ім’я або назва буде показано на візитці?",
        "profession": "Чим ви займаєтеся? Це буде вказано на візитці.",
        "profession_required": "Напишіть, будь ласка, чим ви займаєтеся.",
        "media_question": "Що використати на візитці? Можна вибрати фото, логотип або варіант без зображення.",
        "photo": "Фото", "logo": "Логотип", "no_image": "Без зображення",
        "send_media": "Надішліть {kind} для візитки.",
        "media_required": "Виберіть варіант кнопкою або прикріпіть зображення після вибору фото/логотипа.",
        "about_prompt": "Розкажіть, що людині важливо дізнатися про вас насамперед.\n\nМожна написати, чим ви займаєтеся, як допомагаєте, працюєте онлайн чи офлайн, у яких містах приймаєте та іншу важливу робочу інформацію.\n\nДо 600 символів.",
        "show_examples": "Показати приклади", "examples_title": "<b>Приклади опису</b>",
        "examples_body": "<b>Коуч:</b> допомагаю не загубитися між роботою, стосунками та власними бажаннями. Разом знаходимо опору, ясність і наступний крок.\n\n<b>Масажист:</b> працюю з напругою в тілі, відновленням і дбайливою турботою про себе. Підбираю формат масажу під самопочуття та запит.\n\n<b>Блогер та інфлюенсер:</b> створюю контент про подорожі, стиль життя та красиві місця Києва. Співпрацюю з брендами.",
        "social_prompt": "Виберіть потрібні пункти, потім натисніть «Готово ✓» - після цього заповните посилання по черзі.",
        "other_social": "Інша соцмережа (назва + посилання)", "send_social": "Надішліть посилання на <b>{name}</b>.", "next_social": "Тепер посилання на <b>{name}</b>.",
        "contacts_prompt": "Додайте потрібні контакти або месенджери. Після кожного збереженого контакту ви повернетеся сюди.", "contacts_done": "Готово ✓ · Контакти: {count}",
        "phone": "Телефон", "email": "Email", "other_contact": "Інший контакт",
        "send_contact": "Надішліть контакт для <b>{name}</b>.",
        "other_name": "Напишіть назву месенджера або іншого способу зв’язку. Наприклад: Signal або Discord.",
        "other_name_required": "Напишіть назву месенджера або способу зв’язку.",
        "other_value": "Тепер надішліть контакт або посилання для <b>{name}</b>.",
        "other_value_required": "Надішліть контакт або посилання чи поверніться назад.",
        "phones_prompt": "Додайте потрібні номери телефону. Кожен номер матиме зрозумілу позначку.", "phone_label_prompt": "Напишіть підпис для цього номера. Наприклад: «Салон на Подолі» або «Для запису».", "phone_label_required": "Підпис для номера обов'язковий. Напишіть його або поверніться назад.",
        "phone_work": "Робочий", "phone_personal": "Особистий", "phone_salon": "Салон", "phone_other": "Інший",
        "phone_value": "Номер телефону - <b>{label}</b>:", "phone_required": "Напишіть номер телефону або поверніться назад.", "email_value_prompt": "Напишіть Email.", "email_required": "Напишіть Email або поверніться назад.", "email_existing_label_prompt": "Напишіть підпис для вже доданого Email <b>{value}</b>.", "email_new_label_prompt": "Напишіть підпис для нового Email.", "email_label_required": "Підпис для Email обов'язковий. Напишіть його або поверніться назад.",
        "projects_prompt": "Додайте проєкти та посилання: сайти, боти, портфоліо, курси, акції або інші зовнішні ресурси.\n\nМожна додати кілька проєктів або посилань. Після кожного бот запропонує додати наступний.",
        "add_project": "＋ Додати проєкт або посилання", "project_name": "Назва проєкту або посилання:",
        "project_name_required": "Назва проєкту або посилання обов’язкова. Напишіть її, будь ласка.",
        "project_description": "Опис (необов’язково). Надішліть «-», щоб пропустити.",
        "project_url": "Посилання на проєкт обов’язкове. Вкажіть повну адресу з http:// або https://.",
        "project_url_required": "Посилання на проєкт обов’язкове. Вкажіть його з http:// або https://.",
        "project_url_invalid": "Вкажіть коректне посилання з http:// або https://.", "project_added": "Проєкт або посилання додано.",
        "link_title": "<b>Адреса вашої візитки</b>",
        "link_prompt": "Якщо хочете, вкажіть коротке ім’я для посилання. Наприклад: <code>anna-koval</code> → <code>anna-koval.my-webcard.workers.dev</code>.\n\nЦе побажання до адреси: доступність ми перевіримо пізніше. Цей крок можна пропустити.",
        "review_title": "<b>Перевірте дані візитки.</b>", "sections": "Розділи", "preferred_link": "Бажане ім’я посилання", "name": "Ім’я", "profession_label": "Професія", "card_languages": "Мова", "image": "Зображення", "social_label": "Соцмережі", "contacts_label": "Контакти", "phones_label": "Телефони", "projects_label": "Проєкти та посилання", "price": "Вартість",
        "review_note": "Після надсилання ми перевіримо дані та надішлемо реквізити для вибраного способу оплати.",
        "edit": "✎ Змінити", "edit_prompt": "Що хочете змінити?", "continue_submission": "Продовжити до надсилання",
        "final_comment": "<b>Є запитання, коментар або додаткова інформація?</b>\n\nЯкщо хочете щось уточнити або додати те, для чого не знайшли відповідного поля, напишіть це одним повідомленням. Цей крок можна пропустити.",
        "comment_saved": "Коментар збережено.", "back_review": "← Повернутися до перевірки", "skip_continue": "Пропустити й продовжити",
        "payment_prompt": "<b>Виберіть зручний спосіб оплати</b>\n\nПісля перевірки заявки ми надішлемо реквізити для вибраного способу. Автоматичної оплати в боті немає.",
        "crypto": "Криптовалюта", "payment_other": "Інший спосіб", "payment_other_prompt": "Напишіть зручний спосіб оплати.",
        "confirmation": "<b>Підтвердьте надсилання заявки.</b>\n\nВартість: <b>{tariff}</b>\nСпосіб оплати: <b>{method}</b>",
        "change_payment": "← Змінити спосіб оплати", "submit": "Надіслати заявку",
        "cancelled": "Заявку скасовано. Коли будете готові, надішліть /start.",
        "success": "<b>Готово, заявку отримано.</b>\n\nМи отримали дані та перевіримо інформацію. Потім надішлемо реквізити для вибраного способу оплати. Після оплати підготуємо попереднє посилання на візитку. Ви перевірите її, повідомите потрібні правки, підтвердите результат і отримаєте фінальну візитку.",
        "persistence_error": "Не вдалося автоматично передати заявку. Напишіть нам напряму.", "draft_error": "Заявку отримано, але дані потребують додаткової перевірки. Ми зв’яжемося з вами, щоб усе уточнити.", "support": "Є запитання? Написати в підтримку",
    },
    "en": {
        "back": "← Back", "cancel": "✕ Cancel", "cancel_application": "Cancel application", "done": "Done ✓", "continue": "Continue", "skip": "Skip",
        "not_selected": "not selected", "not_specified": "not specified", "not_added": "none added", "step": "Step {current} of {total}", "current_section": "Current section", "core_section": "Core information", "review_section": "Review and submission",
        "start_intro": "<b>RIAKHIN CARD - digital business card.</b>\n\nOne link with your essential information, contacts, and the ways people can reach you.\n\nFirst choose the card language.\nThen select the sections you want to add.\n\nYou will need your name, professional field, description, and a photo, logo, or no-image option.",
        "interface_language": "<b>Bot interface language</b>",
        "price_intro": "<b>Card price</b>\n\nOne language: <b>1200 грн / $29</b>\nTwo languages: <b>1700 грн / $39</b>\n\nFirst choose the language of the card itself. This is separate from the bot interface language.",
        "card_language_count": "How many languages do you need for the card?\n\nTwo languages work well if you work with people in different languages or want to share one link with different clients.\n\nOne language: 1200 UAH / $29\nTwo languages: 1700 UAH / $39",
        "one_language": "One language", "two_languages": "Two languages", "other_language": "Other language",
        "choose_card_language": "Choose the card language.", "choose_two_card_languages": "Choose two languages for the card. A language switch will appear next to the name and photo.",
        "confirm_language": "Confirm language ✓", "confirm_two_languages": "Confirm 2 languages ✓", "choose_language": "Choose a language", "choose_two_languages": "Choose 2 languages",
        "custom_language_prompt": "Enter the language you need. For example: Polski, Deutsch, or Español.", "custom_language_added": "Language added. Confirm your choice or select one more language.", "select_exact_languages": "Please select the required number of languages.",
        "modules_title": "<b>What will be on the card?</b>\n\n<b>Core information - required:</b> name/brand, professional field, photo/logo/no image, and description.\n\n<b>Optional sections:</b> select only what you want to add.",
        "social": "Social networks", "contacts": "Contacts", "projects": "Projects and links",
        "core_name": "Great. Let’s start with the core information.\n\nWhat name or brand should appear on the card?", "profession": "What do you do? This will appear on the card.", "profession_required": "Please describe what you do.",
        "media_question": "What should appear on the card? Choose a photo, logo, or no image.", "photo": "Photo", "logo": "Logo", "no_image": "No image", "send_media": "Send the {kind} for the card.", "media_required": "Choose an option or attach an image after selecting photo or logo.",
        "about_prompt": "What should people know about you first?\n\nYou can describe what you do, how you help, whether you work online or offline, the cities where you work, and other useful professional information.\n\nUp to 600 characters.",
        "show_examples": "Show examples", "examples_title": "<b>Description examples</b>", "examples_body": "<b>Coach:</b> I help people find clarity and their next step when work, relationships, and personal needs pull in different directions.\n\n<b>Massage therapist:</b> I work with physical tension, recovery, and mindful self-care. I tailor each session to the person’s needs.\n\n<b>Blogger and influencer:</b> I create content about travel, lifestyle, and beautiful places in Kyiv. I collaborate with brands.",
        "social_prompt": "Select the items you need, then tap “Done ✓” and enter each link in turn.", "other_social": "Other social network (name + link)", "send_social": "Send the link for <b>{name}</b>.", "next_social": "Now send the link for <b>{name}</b>.",
        "contacts_prompt": "Add the contacts or messengers you need. After each saved contact, you will return here.", "contacts_done": "Done ✓ · Contacts: {count}", "phone": "Phone", "email": "Email", "other_contact": "Other contact", "send_contact": "Send the contact for <b>{name}</b>.",
        "other_name": "Enter the messenger or contact method name. For example: Signal or Discord.", "other_name_required": "Enter the messenger or contact method name.", "other_value": "Now send the contact or link for <b>{name}</b>.", "other_value_required": "Send the contact or link, or go back.",
        "phones_prompt": "Add the phone numbers you need. Each number will have a clear label.", "phone_label_prompt": "Write a label for this phone number. For example: “Studio in Podil” or “For appointments”.", "phone_label_required": "A phone label is required. Write it or go back.", "phone_work": "Work", "phone_personal": "Personal", "phone_salon": "Studio", "phone_other": "Other", "phone_value": "Phone number - <b>{label}</b>:", "phone_required": "Enter a phone number or go back.", "email_value_prompt": "Enter an email address.", "email_required": "Enter an email address or go back.", "email_existing_label_prompt": "Write a label for the email already added: <b>{value}</b>.", "email_new_label_prompt": "Write a label for the new email address.", "email_label_required": "An email label is required. Write it or go back.",
        "projects_prompt": "Add projects and links: websites, bots, portfolios, courses, promotions, or other external resources.\n\nYou can add several projects or links. After each one, the bot will let you add another.", "add_project": "＋ Add project or link", "project_name": "Project or link name:", "project_name_required": "A project or link name is required.", "project_description": "Description (optional). Send “-” to skip.", "project_url": "The project URL is required. Enter the full address with http:// or https://.", "project_url_required": "A project URL is required. Enter it with http:// or https://.", "project_url_invalid": "Enter a valid URL with http:// or https://.", "project_added": "Project or link added.",
        "link_title": "<b>Your card address</b>", "link_prompt": "If you want, enter a short name for the link. For example: <code>anna-koval</code> → <code>anna-koval.my-webcard.workers.dev</code>.\n\nThis is a preferred address; availability will be checked later. You can skip this step.",
        "review_title": "<b>Review your card details.</b>", "sections": "Sections", "preferred_link": "Preferred link name", "name": "Name", "profession_label": "Profession", "card_languages": "Language", "image": "Image", "social_label": "Social networks", "contacts_label": "Contacts", "phones_label": "Phones", "projects_label": "Projects and links", "price": "Price", "review_note": "After submission, we will review the details and send payment instructions for the selected method.",
        "edit": "✎ Edit", "edit_prompt": "What would you like to change?", "continue_submission": "Continue to submission",
        "final_comment": "<b>Any questions, comments, or additional information?</b>\n\nIf you want to clarify something or add information that did not fit another field, send it in one message. You can skip this step.", "comment_saved": "Comment saved.", "back_review": "← Back to review", "skip_continue": "Skip and continue",
        "payment_prompt": "<b>Choose a payment method</b>\n\nAfter reviewing the application, we will send payment instructions for the selected method. There is no automatic payment in the bot.", "crypto": "Crypto", "payment_other": "Other", "payment_other_prompt": "Enter your preferred payment method.",
        "confirmation": "<b>Confirm application submission.</b>\n\nPrice: <b>{tariff}</b>\nPayment method: <b>{method}</b>", "change_payment": "← Change payment method", "submit": "Submit application",
        "cancelled": "Application cancelled. Send /start when you are ready.",
        "success": "<b>Done, we received your application.</b>\n\nWe received the information and will review it. Then we will send payment instructions for the selected method. After payment, we will prepare a preview card link. You can review it, request necessary corrections, approve the result, and receive the final card.",
        "persistence_error": "We could not submit the application automatically. Contact us directly.", "draft_error": "We received the application, but the details require an additional review. We will contact you to clarify everything.", "support": "Have a question? Contact support",
    },
}


def normalize_language(language: str | None) -> str:
    return language if language in SUPPORTED_LANGUAGES else FALLBACK_LANGUAGE


def language_from_telegram(language_code: str | None) -> str:
    """Resolve Telegram's optional IETF language tag to a Pilot language."""
    if not language_code:
        return FALLBACK_LANGUAGE
    primary_language = language_code.strip().lower().replace("_", "-").split("-", 1)[0]
    return primary_language if primary_language in SUPPORTED_LANGUAGES else FALLBACK_LANGUAGE


def language_from(data: dict | None) -> str:
    return normalize_language((data or {}).get("interface_language"))


def t(language: str | None, key: str, **params) -> str:
    language = normalize_language(language)
    value = COPY.get(language, {}).get(key)
    if value is None:
        value = RU_COPY[key]
    return value.format(**params)


RU_COPY = {
    key: value
    for key, value in {
        "back": "← Назад", "cancel": "✕ Отменить", "cancel_application": "Отменить заявку", "done": "Готово ✓", "continue": "Продолжить", "skip": "Пропустить",
        "not_selected": "не выбрано", "not_specified": "не указано", "not_added": "не добавлены", "step": "Шаг {current} из {total}", "current_section": "Текущий раздел", "core_section": "Основная информация", "review_section": "Проверка и отправка",
        "start_intro": "<b>RIAKHIN CARD - цифровая визитка.</b>\n\nОдна ссылка, где собрана основная информация о вас, контакты и нужные способы связи.\n\nСначала выберите язык визитки.\nЗатем выберите разделы, которые хотите добавить.\n\nДля заполнения понадобятся имя, сфера работы, описание и фото, логотип или вариант без изображения.",
        "interface_language": "<b>Язык общения в боте</b>", "price_intro": "<b>Стоимость визитки</b>\n\nОдин язык: <b>1200 грн / $29</b>\nДва языка: <b>1700 грн / $39</b>\n\nСначала выберите язык самой визитки. Это отдельный выбор от языка общения в боте.",
        "card_language_count": "Сколько языков нужно для визитки?\n\nДва языка подойдут, если вы работаете с аудиторией на разных языках или хотите отправлять одну визитку разным клиентам.\n\nОдин язык: 1200 грн / $29\nДва языка: 1700 грн / $39",
        "one_language": "Один язык", "two_languages": "Два языка", "other_language": "Другой язык", "choose_card_language": "Выберите язык визитки.", "choose_two_card_languages": "Выберите два языка для визитки. На странице появится переключатель возле имени и фото.", "confirm_language": "Подтвердить язык ✓", "confirm_two_languages": "Подтвердить 2 языка ✓", "choose_language": "Выберите язык", "choose_two_languages": "Выберите 2 языка", "custom_language_prompt": "Напишите нужный язык. Например: Polski, Deutsch или Español.", "custom_language_added": "Язык добавлен. Подтвердите выбор или выберите ещё один язык.", "select_exact_languages": "Выберите, пожалуйста, нужное количество языков.",
        "modules_title": "<b>Что будет в визитке?</b>\n\n<b>Основная информация - обязательно:</b> имя/бренд, сфера работы, фото/логотип/без изображения и описание.\n\n<b>Дополнительные разделы:</b> выберите только то, что хотите добавить.", "social": "Социальные сети", "contacts": "Контакты", "projects": "Проекты и ссылки",
        "core_name": "Отлично. Начнём с основной информации.\n\nКакое имя или название будет показано на визитке?", "profession": "Чем вы занимаетесь? Это будет указано на визитке.", "profession_required": "Напишите, пожалуйста, чем вы занимаетесь.", "media_question": "Что использовать на визитке? Можно выбрать фото, логотип или вариант без изображения.", "photo": "Фото", "logo": "Логотип", "no_image": "Без изображения", "send_media": "Пришлите {kind} для визитки.", "media_required": "Выберите вариант кнопкой или прикрепите изображение после выбора фото/логотипа.",
        "about_prompt": "Расскажите, что человеку важно узнать о вас в первую очередь.\n\nМожно написать, чем вы занимаетесь, как помогаете, работаете онлайн или офлайн, в каких городах принимаете и другую важную рабочую информацию.\n\nДо 600 символов.", "show_examples": "Посмотреть примеры", "examples_title": "<b>Примеры описания</b>", "examples_body": "<b>Коуч:</b> помогаю не потеряться между работой, отношениями и своими желаниями. Вместе находим опору, ясность и следующий шаг.\n\n<b>Массажист:</b> работаю с напряжением в теле, восстановлением и бережной заботой о себе. Подбираю формат массажа под самочувствие и запрос.\n\n<b>Блогер и инфлюенсер:</b> создаю контент о путешествиях, стиле жизни и красивых местах Киева. Сотрудничаю с брендами.",
        "social_prompt": "Выберите нужные пункты, затем нажмите «Готово ✓» - после этого заполните ссылки по очереди.", "other_social": "Другая соцсеть (название + ссылка)", "send_social": "Пришлите ссылку на <b>{name}</b>.", "next_social": "Теперь ссылку на <b>{name}</b>.", "contacts_prompt": "Добавьте нужные контакты или мессенджеры. После каждого сохранённого контакта вы вернётесь сюда.", "contacts_done": "Готово ✓ · Контакты: {count}", "phone": "Телефон", "email": "Email", "other_contact": "Другой контакт", "send_contact": "Пришлите контакт для <b>{name}</b>.", "other_name": "Напишите название мессенджера или другого способа связи. Например: Signal или Discord.", "other_name_required": "Напишите название мессенджера или способа связи.", "other_value": "Теперь пришлите контакт или ссылку для <b>{name}</b>.", "other_value_required": "Пришлите контакт или ссылку либо вернитесь назад.",
        "phones_prompt": "Добавьте нужные номера телефона. У каждого номера будет понятная подпись.", "phone_label_prompt": "Напишите подпись для этого номера. Например: «Салон на Подоле» или «Для записи».", "phone_label_required": "Подпись для номера обязательна. Напишите её или вернитесь назад.", "phone_work": "Рабочий", "phone_personal": "Личный", "phone_salon": "Салон", "phone_other": "Другой", "phone_value": "Номер телефона - <b>{label}</b>:", "phone_required": "Напишите номер телефона или вернитесь назад.", "email_value_prompt": "Напишите Email.", "email_required": "Напишите Email или вернитесь назад.", "email_existing_label_prompt": "Напишите подпись для уже добавленного Email <b>{value}</b>.", "email_new_label_prompt": "Напишите подпись для нового Email.", "email_label_required": "Подпись для Email обязательна. Напишите её или вернитесь назад.",
        "projects_prompt": "Добавьте проекты и ссылки: сайты, боты, портфолио, курсы, акции или другие внешние ресурсы.\n\nМожно добавить несколько проектов или ссылок. После каждого бот предложит добавить следующий.", "add_project": "＋ Добавить проект или ссылку", "project_name": "Название проекта или ссылки:", "project_name_required": "Название проекта или ссылки обязательно. Напишите его, пожалуйста.", "project_description": "Описание (необязательно). Отправьте «-», чтобы пропустить.", "project_url": "Ссылка на проект обязательна. Укажите полный адрес с http:// или https://.", "project_url_required": "Ссылка на проект обязательна. Укажите её с http:// или https://.", "project_url_invalid": "Укажите корректную ссылку с http:// или https://.", "project_added": "Проект или ссылка добавлены.",
        "link_title": "<b>Адрес вашей визитки</b>", "link_prompt": "Если хотите, укажите короткое имя для ссылки. Например: <code>anna-koval</code> → <code>anna-koval.my-webcard.workers.dev</code>.\n\nЭто пожелание к адресу: доступность мы проверим позже. Этот шаг можно пропустить.",
        "review_title": "<b>Проверьте данные визитки.</b>", "sections": "Разделы", "preferred_link": "Желаемое имя ссылки", "name": "Имя", "profession_label": "Профессия", "card_languages": "Язык", "image": "Изображение", "social_label": "Соцсети", "contacts_label": "Контакты", "phones_label": "Телефоны", "projects_label": "Проекты и ссылки", "price": "Стоимость", "review_note": "После отправки мы проверим данные и пришлём реквизиты для выбранного способа оплаты.", "edit": "✎ Изменить", "edit_prompt": "Что хотите изменить?", "continue_submission": "Продолжить к отправке",
        "final_comment": "<b>Есть вопрос, комментарий или дополнительная информация?</b>\n\nЕсли хотите что-то уточнить или добавить то, для чего не нашли подходящего поля, напишите это одним сообщением. Этот шаг можно пропустить.", "comment_saved": "Комментарий сохранён.", "back_review": "← Вернуться к проверке", "skip_continue": "Пропустить и продолжить", "payment_prompt": "<b>Выберите удобный способ оплаты</b>\n\nПосле проверки заявки мы пришлём реквизиты выбранным способом. Автоматической оплаты в боте нет.", "crypto": "Криптовалюта", "payment_other": "Другой способ", "payment_other_prompt": "Напишите удобный способ оплаты.", "confirmation": "<b>Подтвердите отправку заявки.</b>\n\nСтоимость: <b>{tariff}</b>\nСпособ оплаты: <b>{method}</b>", "change_payment": "← Изменить способ оплаты", "submit": "Отправить заявку", "cancelled": "Заявка отменена. Когда будете готовы, отправьте /start.", "success": "<b>Готово, заявку получили.</b>\n\nМы получили данные и проверим информацию. Затем пришлём реквизиты для выбранного способа оплаты. После оплаты подготовим предварительную ссылку на визитку. Вы проверите её, сообщите необходимые правки, подтвердите итог и получите финальную визитку.", "persistence_error": "Не получилось передать заявку автоматически. Напишите нам напрямую.", "draft_error": "Заявку получили, но данные требуют дополнительной проверки. Мы свяжемся с вами, чтобы всё уточнить.", "support": "Есть вопрос? Написать в поддержку",
    }.items()
}

RU_COPY["email_new_label_prompt"] = (
    "Как подписать этот Email?\n\n"
    "Например: Рабочий, Личный, Для заказов.\n\n"
    "Если подпись не нужна, отправьте -"
)
