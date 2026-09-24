#include <fcitx/addonfactory.h>
#include <fcitx/addonmanager.h>
#include <fcitx/inputcontext.h>
#include <fcitx/inputpanel.h>
#include <fcitx/instance.h>
#include <fcitx-config/iniparser.h>
#include <fcitx-utils/dbus/objectvtable.h>
#include <fcitx-utils/dbus/servicewatcher.h>
#include <fcitx-utils/event.h>
#include <fcitx-utils/utf8.h>
#include <dbus_public.h>
#include <sys/random.h>
#include <array>
#include <chrono>
#include <memory>
#include <stdexcept>
#include <string>
#include <vector>

FCITX_CONFIGURATION(VoiceConfig,
    fcitx::Option<bool> hotkeys{this, "EnableHotkeys", "Enable Right Alt voice shortcuts", false};
    fcitx::Option<int, fcitx::IntConstrain> holdMs{this, "HoldThresholdMs", "Hold threshold (ms)",
                                                250, fcitx::IntConstrain(100, 2000)};
);

// Doubao's audio process receives a single-use capability for the focused field.
// The D-Bus sender, field lifetime and expiration are checked again at delivery.
class Dictation final : public fcitx::AddonInstance,
                        public fcitx::dbus::ObjectVTable<Dictation> {
    struct Delivery {
        std::string ticket, sender;
        fcitx::TrackableObjectReference<fcitx::InputContext> field;
        std::chrono::steady_clock::time_point expires;
        bool preview = false;
    };
    fcitx::Instance *instance;
    std::unique_ptr<Delivery> pending;
    std::unique_ptr<fcitx::dbus::ServiceWatcher> serviceWatcher;
    std::unique_ptr<fcitx::dbus::ServiceWatcherEntry> ownerWatch;
    std::vector<std::unique_ptr<fcitx::HandlerTableEntry<fcitx::EventHandler>>> listeners;
    VoiceConfig config;
    fcitx::TrackableObjectReference<fcitx::InputContext> hotkeyField;
    std::unique_ptr<fcitx::EventSourceTime> holdTimer;
    bool altDown = false, holdStarted = false, chordUsed = false, spaceDown = false;

    static std::string contextId(fcitx::InputContext *field) {
        std::string id;
        if (field) for (auto byte : field->uuid()) {
            id += "0123456789abcdef"[byte / 16];
            id += "0123456789abcdef"[byte % 16];
        }
        return id;
    }
    void resetHotkey() {
        if (holdTimer) holdTimer->setEnabled(false);
        altDown = holdStarted = chordUsed = spaceDown = false;
        hotkeyField.unwatch();
    }
    bool hotkey(fcitx::KeyEvent &key) {
        if (!*config.hotkeys) return false;
        auto sym = key.rawKey().sym();
        auto *field = key.inputContext();
        if (key.rawKey().states().test(fcitx::KeyState::Repeat) &&
            ((sym == FcitxKey_Alt_R && altDown) || (sym == FcitxKey_space && spaceDown))) {
            key.filterAndAccept(); return true;
        }
        if (sym == FcitxKey_Alt_R) {
            if (key.isRelease()) {
                if (!altDown) return false;
                if (holdStarted && !chordUsed)
                    shortcut("hold-stop", contextId(hotkeyField.get()));
                // Keep an already captured Space release paired with its press.
                bool space = spaceDown;
                resetHotkey(); spaceDown = space;
                key.filterAndAccept(); return true;
            }
            if (altDown) { key.filterAndAccept(); return true; }
            auto modifiers = fcitx::KeyStates(fcitx::KeyState::Ctrl) | fcitx::KeyState::Shift |
                             fcitx::KeyState::Super | fcitx::KeyState::Super2;
            if (!eligible(field) || key.rawKey().states().testAny(modifiers) ||
                ((!pending || pending->field.get() != field || !pending->preview) &&
                 (!field->inputPanel().clientPreedit().toString().empty() ||
                  !field->inputPanel().preedit().toString().empty()))) return false;
            altDown = true; hotkeyField = field->watch();
            holdTimer = instance->eventLoop().addTimeEvent(CLOCK_MONOTONIC,
                fcitx::now(CLOCK_MONOTONIC) + *config.holdMs * 1000, 0,
                [this](fcitx::EventSourceTime *, uint64_t) {
                    if (altDown && !chordUsed && eligible(hotkeyField.get())) {
                        holdStarted = true;
                        shortcut("hold-start", contextId(hotkeyField.get()));
                    }
                    return false;
                });
            key.filterAndAccept(); return true;
        }
        if (sym == FcitxKey_space && key.isRelease() && spaceDown) {
            spaceDown = false; key.filterAndAccept(); return true;
        }
        if (!altDown || key.isRelease()) return false;
        if (holdTimer) holdTimer->setEnabled(false);
        auto modifiers = fcitx::KeyStates(fcitx::KeyState::Ctrl) | fcitx::KeyState::Shift |
                         fcitx::KeyState::Super | fcitx::KeyState::Super2;
        if (sym == FcitxKey_space && field == hotkeyField.get() && eligible(field) &&
            !key.rawKey().states().testAny(modifiers)) {
            if (!chordUsed) shortcut("toggle", contextId(field));
            chordUsed = spaceDown = true;
            key.filterAndAccept(); return true;
        }
        if (holdStarted && !chordUsed) shortcut("hold-cancel", contextId(hotkeyField.get()));
        chordUsed = true;
        return false;
    }

    bool eligible(fcitx::InputContext *field) const {
        return field && field->hasFocus() &&
            !field->capabilityFlags().testAny(fcitx::CapabilityFlag::PasswordOrSensitive);
    }
    bool owned(const std::string &ticket) const {
        return pending && pending->ticket == ticket &&
            pending->sender == currentMessage()->sender();
    }
    static bool safeText(const std::string &text) {
        if (text.size() > 65536 || !fcitx::utf8::validate(text)) return false;
        for (unsigned char byte : text) if (byte < 32 || byte == 127) return false;
        return true;
    }
    void clearPreview(Delivery &delivery) {
        auto *field = delivery.field.get();
        if (!delivery.preview || !field) return;
        delivery.preview = false;
        field->inputPanel().setClientPreedit(fcitx::Text());
        field->inputPanel().setPreedit(fcitx::Text());
        field->updatePreedit();
        field->updateUserInterface(fcitx::UserInterfaceComponent::InputPanel);
    }
    void revoke(const std::string &reason) {
        auto previous = std::move(pending);
        if (previous) {
            clearPreview(*previous);
            invalidatedTo(previous->sender, previous->ticket, reason);
        }
    }
    void observe(fcitx::Event &event) {
        auto &input = static_cast<fcitx::InputContextEvent &>(event);
        if (event.type() == fcitx::EventType::InputContextKeyEvent) {
            if (hotkey(static_cast<fcitx::KeyEvent &>(event))) return;
        } else if (input.inputContext() == hotkeyField.get()) {
            if (holdStarted) shortcut("hold-cancel", contextId(hotkeyField.get()));
            resetHotkey();
        }
        if (!pending) return;
        if (input.inputContext() != pending->field.get()) return;
        switch (event.type()) {
        case fcitx::EventType::InputContextKeyEvent: {
            auto &key = static_cast<fcitx::KeyEvent &>(event);
            if (key.isRelease() || key.key().isModifier()) return;
            if (key.key().sym() == FcitxKey_Escape) key.filterAndAccept();
            revoke("typing");
            break;
        }
        case fcitx::EventType::InputContextCapabilityChanged:
            if (!eligible(input.inputContext())) revoke("sensitive-field");
            break;
        default:
            revoke("input-context-changed");
        }
    }
public:
    explicit Dictation(fcitx::Instance *core) : instance(core) {
        reloadConfig();
        auto *module = instance->addonManager().addon("dbus", true);
        if (!module || !module->call<fcitx::IDBusModule::bus>()->addObjectVTable(
                "/org/fcitx/Fcitx5/DoubaoDictation", "org.fcitx.Fcitx5.DoubaoDictation1", *this))
            throw std::runtime_error("Doubao dictation D-Bus endpoint unavailable");
        serviceWatcher = std::make_unique<fcitx::dbus::ServiceWatcher>(
            *module->call<fcitx::IDBusModule::bus>());
        for (auto type : {fcitx::EventType::InputContextFocusOut,
                          fcitx::EventType::InputContextDestroyed,
                          fcitx::EventType::InputContextReset,
                          fcitx::EventType::InputContextCapabilityChanged,
                          fcitx::EventType::InputContextKeyEvent})
            listeners.emplace_back(instance->watchEvent(type, fcitx::EventWatcherPhase::PreInputMethod,
                [this](fcitx::Event &event) { observe(event); }));
    }
    const fcitx::Configuration *getConfig() const override { return &config; }
    void reloadConfig() override {
        if (holdStarted) shortcut("hold-cancel", contextId(hotkeyField.get()));
        resetHotkey();
        fcitx::readAsIni(config, "conf/doubaovoice.conf");
    }
    void setConfig(const fcitx::RawConfig &raw) override {
        if (holdStarted) shortcut("hold-cancel", contextId(hotkeyField.get()));
        resetHotkey();
        config.load(raw, true);
        fcitx::safeSaveAsIni(config, "conf/doubaovoice.conf");
    }
    std::string beginForContext(const std::string &context) {
        auto *field = instance->mostRecentInputContext();
        if (context.empty() || contextId(field) != context) return {};
        return begin();
    }
    std::string begin() {
        auto *field = instance->mostRecentInputContext();
        if (!eligible(field)) return {};
        revoke("new-dictation");
        if (!field->inputPanel().clientPreedit().toString().empty() ||
            !field->inputPanel().preedit().toString().empty()) return {};
        auto delivery = std::make_unique<Delivery>();
        std::array<unsigned char, 24> bytes{};
        if (getrandom(bytes.data(), bytes.size(), 0) != static_cast<ssize_t>(bytes.size()))
            throw std::runtime_error("Cannot allocate dictation ticket");
        for (auto byte : bytes) {
            delivery->ticket += "0123456789abcdef"[byte / 16];
            delivery->ticket += "0123456789abcdef"[byte % 16];
        }
        delivery->sender = currentMessage()->sender();
        delivery->field = field->watch();
        delivery->expires = std::chrono::steady_clock::now() + std::chrono::seconds(180);
        pending = std::move(delivery);
        ownerWatch = serviceWatcher->watchService(pending->sender,
            [this](const std::string &name, const std::string &, const std::string &owner) {
                if (owner.empty() && pending && pending->sender == name) revoke("owner-disconnected");
            });
        return pending->ticket;
    }
    bool valid(const std::string &ticket) const {
        return owned(ticket) && eligible(pending->field.get()) &&
               std::chrono::steady_clock::now() < pending->expires;
    }
    bool cancel(const std::string &ticket) {
        if (!owned(ticket)) return false;
        auto delivery = std::move(pending);
        clearPreview(*delivery);
        return true;
    }
    bool preview(const std::string &ticket, const std::string &text) {
        if (!valid(ticket) || !safeText(text)) return false;
        auto *field = pending->field.get();
        fcitx::Text preedit(text, fcitx::TextFormatFlags(fcitx::TextFormatFlag::Underline) |
                                  fcitx::TextFormatFlag::DontCommit);
        preedit.setCursor(text.size());
        pending->preview = true;
        field->inputPanel().setClientPreedit(preedit);
        field->inputPanel().setPreedit(preedit);
        field->updatePreedit();
        field->updateUserInterface(fcitx::UserInterfaceComponent::InputPanel);
        return true;
    }
    bool commit(const std::string &ticket, const std::string &text) {
        if (!owned(ticket)) return false;
        bool accepted = valid(ticket) && !text.empty() && safeText(text);
        auto delivery = std::move(pending);
        clearPreview(*delivery);
        if (accepted) delivery->field.get()->commitString(text);
        return accepted;
    }
    FCITX_OBJECT_VTABLE_METHOD(begin, "Begin", "", "s");
    FCITX_OBJECT_VTABLE_METHOD(beginForContext, "BeginForContext", "s", "s");
    FCITX_OBJECT_VTABLE_METHOD(valid, "Valid", "s", "b");
    FCITX_OBJECT_VTABLE_METHOD(cancel, "Cancel", "s", "b");
    FCITX_OBJECT_VTABLE_METHOD(preview, "Preview", "ss", "b");
    FCITX_OBJECT_VTABLE_METHOD(commit, "Commit", "ss", "b");
    FCITX_OBJECT_VTABLE_SIGNAL(invalidated, "Invalidated", "ss");
    FCITX_OBJECT_VTABLE_SIGNAL(shortcut, "Shortcut", "ss");
};

class Factory : public fcitx::AddonFactory {
public:
    fcitx::AddonInstance *create(fcitx::AddonManager *manager) override {
        return new Dictation(manager->instance());
    }
};
FCITX_ADDON_FACTORY(Factory);
