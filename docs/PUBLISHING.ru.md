# Публикация Bridge на GitHub

## 1. Что уже подготовлено

- Английский README с баннером и кнопками. Ссылки относительные и работают после загрузки в репозиторий.
- Исходники интерфейса, Python, macOS-помощника и Android.
- .gitignore исключает окружения, SDK, сборки, журналы и ключи подписи.
- Workflow «Desktop packages» собирает Windows EXE вручную через Actions.
- Готовые пакеты находятся в dist. Исходный архив Bridge-source.zip содержит файлы для репозитория.

Код на GitHub ещё не отправлен. Репозиторий и релизы нужно создать в своём аккаунте.

## 2. Создание репозитория

Войдите на github.com, нажмите «+» → «New repository». Назовите репозиторий bridge, выберите Public или Private. Оставьте создание README, .gitignore и лицензии выключенным: первые два файла уже подготовлены. Нажмите Create repository.

Для публикации собственного кода выберите лицензию осознанно. Сейчас файл LICENSE для Bridge отсутствует. При публичном размещении это ограничивает права других людей на повторное использование кода. Лицензии встроенных зависимостей действуют отдельно.

## 3. Загрузка исходников

Рекомендуемый вариант — распаковать dist/Bridge-source.zip в новую папку, чтобы загрузить только подготовленные файлы. В терминале перейдите в эту папку:

```sh
git init -b main
git add .
git status
git commit -m "Initial Bridge source"
git remote add origin https://github.com/YOUR_USERNAME/bridge.git
git push -u origin main
```

Замените YOUR_USERNAME своим именем на GitHub. Для входа используйте GitHub Desktop, GitHub CLI с командой gh auth login или настроенный Git Credential Manager. Обычный пароль аккаунта не подходит для HTTPS Git push.

При запросе автора коммита задайте локальные git config user.name и git config user.email. Можно использовать приватный noreply-адрес из GitHub Settings → Emails.

Если используете исходную папку проекта, перед git add проверьте git status --short --ignored. Не добавляйте .toolchains, .venv, bin, dist, каталоги build, журналы, подписки или ключи. Не используйте git add -f для обхода .gitignore.

Альтернатива — GitHub Desktop: File → Add local repository, создайте репозиторий в распакованной папке, сделайте commit и нажмите Publish repository. Проверьте переключатель приватности.

## 4. Первый релиз

Откройте репозиторий → Releases → Draft a new release.

1. Выберите новый тег v0.1.0 и ветку main.
2. Назовите релиз Bridge v0.1.0.
3. Опишите изменения и проверенные платформы.
4. Прикрепите Bridge.exe, Bridge.apk, Bridge-macOS-Intel.zip и SHA256SUMS.txt из dist.
5. Для этой стадии отметьте Set as a pre-release: Android и Windows ещё требуют проверки на реальных устройствах.
6. Сначала сохраните черновик. Проверьте файлы, затем нажмите Publish release.

GitHub добавляет Source code (zip/tar.gz) автоматически по выбранному тегу. Подготовленный исходный архив можно приложить дополнительно.

.app является пакетом-каталогом. Для передачи используйте ZIP, сохраняющий структуру пакета. Подготовленный Bridge-macOS-Intel.zip уже подходит. Релизные файлы размещайте в Releases, чтобы история Git содержала исходники.

Для предварительного релиза используйте ссылку /releases: адрес /releases/latest выбирает обычный релиз и может не вести к pre-release.

## 5. Обновления

Измените код, проверьте приложение, выполните:

```sh
git add .
git commit -m "Describe the change"
git push
```

После сборки создайте новый релиз с тегом v0.1.1. Не заменяйте содержимое уже опубликованного тега. В Android увеличьте versionCode в android/app/build.gradle и задайте versionName. Подписывайте обновления тем же ключом.

Нынешний APK использует отладочный ключ. Для публичного стабильного распространения создайте собственный постоянный ключ подписи, сделайте резервную копию и настройте release signing в Gradle. Переход с debug-ключа на новый ключ потребует переустановки приложения. Ключи и пароли в репозиторий не загружайте. Для CI используйте GitHub Actions secrets.

## 6. Windows-сборка через GitHub Actions

После загрузки исходников откройте Actions → Desktop packages → Run workflow → main → Run workflow.

После успешного завершения скачайте artifact Bridge-Windows, распакуйте его и прикрепите EXE к релизу. Workflow собирает файл, публикация релиза выполняется вручную. Настройка tokens или secrets для этой сборки не требуется. Workflow в этой работе подготовлен, но на вашем GitHub ещё не запускался.

macOS и Android можно собирать по README. Автопубликация не настроена. Для неё сначала определите постоянные ключи подписи и проверку сборок, затем выдайте workflow минимально необходимые права contents: write.

## 7. Оформление страницы

В блоке About укажите описание, например «A compact Python and Xray client for Windows, macOS and Android». Добавьте темы python, xray, vpn-client, material-you, android, macos, windows.

README уже содержит относительные ссылки на Releases и Issues. В Settings → General включите Issues, если хотите принимать отчёты. При необходимости загрузите отдельную картинку для Social preview. SVG-баннер README лежит в docs/banner.svg.

## 8. Проверка перед публикацией

- Откройте README на GitHub и проверьте баннер и кнопки.
- Скачайте каждый релизный файл обратно.
- Сверьте SHA-256 с SHA256SUMS.txt.
- Укажите архитектуры, требования WebView2 и статус тестирования.
- Приложите необходимые уведомления о лицензиях зависимостей. Список отправных точек — docs/THIRD_PARTY.md.
- Убедитесь, что подписки, серверные ключи и ключи подписи отсутствуют в исходниках.

Официальные инструкции:
- https://docs.github.com/en/migrations/importing-source-code/using-the-command-line-to-import-source-code/adding-locally-hosted-code-to-github
- https://docs.github.com/en/repositories/releasing-projects-on-github/managing-releases-in-a-repository

## 9. Постоянная подпись Android для стабильных релизов

Вне папки репозитория создайте ключ через keytool из JDK. Команда запрашивает пароли интерактивно:

```sh
keytool -genkeypair -v -keystore /absolute/private/path/bridge-release.jks -alias bridge -keyalg RSA -keysize 3072 -validity 10000
```

Сделайте резервную копию файла и паролей. Потеря ключа мешает выпускать совместимые обновления для уже установленного APK.

Gradle-проект подготовлен к чтению параметров подписи из переменных окружения. Пример для Bash на macOS/Linux:

```sh
export BRIDGE_KEYSTORE=/absolute/private/path/bridge-release.jks
export BRIDGE_KEY_ALIAS=bridge
read -s -p "Store password: " BRIDGE_STORE_PASSWORD
echo
export BRIDGE_STORE_PASSWORD
read -s -p "Key password: " BRIDGE_KEY_PASSWORD
echo
export BRIDGE_KEY_PASSWORD
python prepare_android.py
gradle -p android assembleRelease
unset BRIDGE_STORE_PASSWORD BRIDGE_KEY_PASSWORD
```

Файл будет в android/app/build/outputs/apk/release/app-release.apk. Проверьте подпись утилитой apksigner из Android SDK Build Tools. Если переменные не заданы, release APK будет неподписанным и потребует подписи перед установкой.

Для GitHub Actions постоянную подпись можно подключить позднее через Secrets. Не вставляйте пароли прямо в workflow, Gradle или команды, сохранённые в истории терминала. Для нынешней локальной сборки постоянный ключ не создавался.
