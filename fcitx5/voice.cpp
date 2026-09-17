#include <fcitx/addonfactory.h>
#include <fcitx/addonmanager.h>
#include <fcitx/inputcontext.h>
#include <fcitx/instance.h>
#include <fcitx-utils/dbus/objectvtable.h>
#include <fcitx-utils/utf8.h>
#include <dbus_public.h>
#include <sys/random.h>
#include <array>
#include <chrono>
#include <memory>
#include <stdexcept>
#include <string>
#include <vector>

// Doubao's audio process receives a single-use capability for the focused field.
// The D-Bus sender, field lifetime and expiration are checked again at delivery.
class Dictation final : public fcitx::AddonInstance,
                        public fcitx::dbus::ObjectVTable<Dictation> {
    struct Delivery {
        std::string ticket, sender;
        fcitx::TrackableObjectReference<fcitx::InputContext> field;
        std::chrono::steady_clock::time_point expires;
    };
    fcitx::Instance *instance;
    std::unique_ptr<Delivery> pending;
    std::vector<std::unique_ptr<fcitx::HandlerTableEntry<fcitx::EventHandler>>> listeners;

    bool eligible(fcitx::InputContext *field) const {
        return field && field->hasFocus() &&
            !field->capabilityFlags().testAny(fcitx::CapabilityFlag::PasswordOrSensitive);
    }
    bool owned(const std::string &ticket) const {
        return pending && pending->ticket == ticket &&
            pending->sender == currentMessage()->sender();
    }
    void revoke(const std::string &reason) {
        auto previous = std::move(pending);
        if (previous) invalidatedTo(previous->sender, previous->ticket, reason);
    }
    void observe(fcitx::Event &event) {
        if (!pending) return;
        auto &input = static_cast<fcitx::InputContextEvent &>(event);
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
        auto *module = instance->addonManager().addon("dbus", true);
        if (!module || !module->call<fcitx::IDBusModule::bus>()->addObjectVTable(
                "/org/fcitx/Fcitx5/DoubaoDictation", "org.fcitx.Fcitx5.DoubaoDictation1", *this))
            throw std::runtime_error("Doubao dictation D-Bus endpoint unavailable");
        for (auto type : {fcitx::EventType::InputContextFocusOut,
                          fcitx::EventType::InputContextDestroyed,
                          fcitx::EventType::InputContextReset,
                          fcitx::EventType::InputContextCapabilityChanged,
                          fcitx::EventType::InputContextKeyEvent})
            listeners.emplace_back(instance->watchEvent(type, fcitx::EventWatcherPhase::PreInputMethod,
                [this](fcitx::Event &event) { observe(event); }));
    }
    std::string begin() {
        auto *field = instance->mostRecentInputContext();
        if (!eligible(field)) return {};
        revoke("new-dictation");
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
        return pending->ticket;
    }
    bool valid(const std::string &ticket) const {
        return owned(ticket) && eligible(pending->field.get()) &&
               std::chrono::steady_clock::now() < pending->expires;
    }
    bool cancel(const std::string &ticket) {
        if (!owned(ticket)) return false;
        pending.reset();
        return true;
    }
    bool commit(const std::string &ticket, const std::string &text) {
        if (!owned(ticket)) return false;
        bool accepted = valid(ticket) && !text.empty() && text.size() <= 65536 && fcitx::utf8::validate(text);
        for (unsigned char byte : text) if (byte < 32 || byte == 127) accepted = false;
        auto delivery = std::move(pending);
        if (accepted) delivery->field.get()->commitString(text);
        return accepted;
    }
    FCITX_OBJECT_VTABLE_METHOD(begin, "Begin", "", "s");
    FCITX_OBJECT_VTABLE_METHOD(valid, "Valid", "s", "b");
    FCITX_OBJECT_VTABLE_METHOD(cancel, "Cancel", "s", "b");
    FCITX_OBJECT_VTABLE_METHOD(commit, "Commit", "ss", "b");
    FCITX_OBJECT_VTABLE_SIGNAL(invalidated, "Invalidated", "ss");
};

class Factory : public fcitx::AddonFactory {
public:
    fcitx::AddonInstance *create(fcitx::AddonManager *manager) override {
        return new Dictation(manager->instance());
    }
};
FCITX_ADDON_FACTORY(Factory);
