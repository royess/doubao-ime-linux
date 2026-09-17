#include <fcitx/addonfactory.h>
#include <fcitx/addonmanager.h>
#include <fcitx/action.h>
#include <fcitx/candidatelist.h>
#include <fcitx/inputcontext.h>
#include <fcitx/inputmethodengine.h>
#include <fcitx/inputpanel.h>
#include <fcitx/instance.h>
#include <fcitx/statusarea.h>
#include <fcitx/userinterface.h>
#include <fcitx-utils/misc.h>
#include <fcitx-utils/standardpath.h>
#include <fcitx-utils/utf8.h>
#include <json-c/json.h>
#include <sys/socket.h>
#include <sys/un.h>
#include <poll.h>
#include <unistd.h>
#include <cerrno>
#include <chrono>
#include <cstring>
#include <cstdlib>
#include <memory>
#include <sstream>
#include <stdexcept>
#include <unordered_set>

struct Reply { int result=0, cursor=0, selected=0; std::string preedit, commit; std::vector<std::string> candidates; };

static Reply request(const std::string &command) {
    const char *configured=std::getenv("DOUBAO_KEYBOARD_SOCKET"), *runtime=std::getenv("XDG_RUNTIME_DIR");
    if (!configured&&!runtime) throw std::runtime_error("Missing runtime directory");
    std::string path=configured?configured:std::string(runtime)+"/doubaoime-keyboard.sock";
    sockaddr_un address{}; address.sun_family=AF_UNIX;
    if(path.size()>=sizeof(address.sun_path))throw std::runtime_error("Socket path too long");
    std::memcpy(address.sun_path,path.c_str(),path.size()+1);
    int fd=socket(AF_UNIX,SOCK_STREAM|SOCK_CLOEXEC|SOCK_NONBLOCK,0);
    if(fd<0)throw std::runtime_error("Cannot create socket");
    struct Close{int fd;~Close(){close(fd);}} closer{fd};
    auto deadline=std::chrono::steady_clock::now()+std::chrono::milliseconds(250);
    auto wait=[&](short events){
        auto left=std::chrono::duration_cast<std::chrono::milliseconds>(deadline-std::chrono::steady_clock::now()).count();
        pollfd p{fd,events,0};
        if(left<=0||poll(&p,1,int(left))<=0)throw std::runtime_error("Engine timeout");
    };
    if(connect(fd,reinterpret_cast<sockaddr*>(&address),sizeof(address))<0){
        if(errno!=EINPROGRESS)throw std::runtime_error("Engine unavailable");
        wait(POLLOUT);int error=0;socklen_t len=sizeof(error);getsockopt(fd,SOL_SOCKET,SO_ERROR,&error,&len);
        if(error)throw std::runtime_error("Engine unavailable");
    }
    std::string outgoing=command+"\n";size_t sent=0;
    while(sent<outgoing.size()){
        wait(POLLOUT);auto n=send(fd,outgoing.data()+sent,outgoing.size()-sent,MSG_NOSIGNAL);
        if(n<0&&errno==EAGAIN)continue;
        if(n<=0)throw std::runtime_error("Engine disconnected");
        sent+=size_t(n);
    }
    std::string data;char buffer[8192];
    while(data.find('\n')==std::string::npos){
        wait(POLLIN);auto n=recv(fd,buffer,sizeof(buffer),0);
        if(n<0&&errno==EAGAIN)continue;
        if(n<=0)throw std::runtime_error("Engine disconnected");
        data.append(buffer,size_t(n));if(data.size()>1000000)throw std::runtime_error("Response too large");
    }
    std::unique_ptr<json_object,decltype(&json_object_put)> object(json_tokener_parse(data.c_str()),json_object_put);
    if(!object)throw std::runtime_error("Invalid engine response");
    auto value=[&](const char *name){json_object *v=nullptr;json_object_object_get_ex(object.get(),name,&v);return v;};
    auto string=[&](const char *name){auto v=value(name);if(!v||!json_object_is_type(v,json_type_string))throw std::runtime_error("Invalid text");
        std::string s=json_object_get_string(v);if(!fcitx::utf8::validate(s))throw std::runtime_error("Invalid UTF-8");return s;};
    Reply r;r.result=json_object_get_int(value("result"));r.cursor=json_object_get_int(value("cursor"));r.selected=json_object_get_int(value("selected"));
    r.preedit=string("preedit");r.commit=string("commit");
    std::istringstream lines(string("candidates"));std::string candidate;
    while(std::getline(lines,candidate))if(!candidate.empty())r.candidates.push_back(candidate);
    if(r.result<0)throw std::runtime_error("Engine rejected request");
    return r;
}

class Engine;
class Word final:public fcitx::CandidateWord {
public:
    Word(Engine *engine,int index,unsigned generation,std::string text):CandidateWord(fcitx::Text(text)),engine_(engine),index_(index),generation_(generation){}
    void select(fcitx::InputContext *ic)const override;
private:Engine *engine_;int index_;unsigned generation_;
};

class Engine final:public fcitx::InputMethodEngine {
public:
    explicit Engine(fcitx::Instance *instance):instance_(instance){
        settingsAction_.setShortText("豆包设置");
        settingsAction_.setIcon("doubao-ime-linux");
        settingsAction_.registerAction("doubao-settings", &instance_->userInterfaceManager());
        settingsConnection_=settingsAction_.connect<fcitx::SimpleAction::Activated>([](fcitx::InputContext *){
            auto desktop=fcitx::StandardPath::global().locate(
                fcitx::StandardPath::Type::Data, "applications/doubao-settings.desktop");
            if(!desktop.empty())fcitx::startProcess({"gio", "launch", desktop});
        });
    }
    void activate(const fcitx::InputMethodEntry &,fcitx::InputContextEvent &event)override {
        if(!fcitx::StandardPath::global().locate(fcitx::StandardPath::Type::Data,
                                               "applications/doubao-settings.desktop").empty()){
            event.inputContext()->statusArea().addAction(fcitx::StatusGroup::InputMethod, &settingsAction_);
            event.inputContext()->updateUserInterface(fcitx::UserInterfaceComponent::StatusArea);
        }
        target_=event.inputContext()->watch();
        if(sensitive(target_.get()))return;
        transact(event.inputContext(),"F");
    }
    void reset(const fcitx::InputMethodEntry &,fcitx::InputContextEvent &event)override {
        if(target_.get()==event.inputContext()){try{request("R");}catch(...){}target_.unwatch();}
        clear(event.inputContext());
    }
    void choose(fcitx::InputContext *ic,int index,unsigned generation){
        if(ic!=target_.get()||generation!=generation_||!ic->hasFocus()||sensitive(ic))return;
        transact(ic,"S "+std::to_string(index));
    }
    void keyEvent(const fcitx::InputMethodEntry &,fcitx::KeyEvent &event)override {
        // Paging is handled locally. Consume its matching release as well:
        // sending it to the engine would rebuild the list at the first page.
        // Track physical keys so changing Shift before release is harmless.
        auto keycode=event.rawKey().code();
        if(event.isRelease()){
            if(pagingKeys_.erase(keycode)){event.filterAndAccept();return;}
        }else pagingKeys_.erase(keycode);
        auto *ic=event.inputContext();
        if(sensitive(ic))return;
        if(event.key().states().testAny(fcitx::KeyStates(fcitx::KeyState::Ctrl)|fcitx::KeyState::Alt|fcitx::KeyState::Super|fcitx::KeyState::Super2)){
            if(!event.isRelease()&&!event.key().isModifier()&&target_.get()==ic){try{request("R");}catch(...){}clear(ic);target_.unwatch();}
            return;
        }
        if(target_.get()!=ic){target_=ic->watch();transact(ic,"F");if(target_.get()!=ic)return;}
        // Normalized Fcitx keys fold Shift+A to a; the engine needs the actual
        // character after layout conversion, including case and shifted symbols.
        auto sym=event.rawKey().sym();auto unicode=fcitx::Key::keySymToUnicode(sym);
        auto candidates=ic->inputPanel().candidateList();
        if(!event.isRelease()&&candidates&&!candidates->empty()){
            int index=unicode>='1'&&unicode<='9'?int(unicode-'1'):-1;
            if(sym==FcitxKey_space)index=candidates->cursorIndex()<0?0:candidates->cursorIndex();
            if(index>=0&&index<candidates->size()){
                candidates->candidate(index).select(ic);event.filterAndAccept();return;
            }
            if(sym==FcitxKey_equal||sym==FcitxKey_minus){
                auto *pages=candidates->toPageable();
                if(pages){if(sym==FcitxKey_equal)pages->next();else pages->prev();
                    pagingKeys_.insert(keycode);
                    ic->updateUserInterface(fcitx::UserInterfaceComponent::InputPanel);event.filterAndAccept();return;}
            }
            if(sym==FcitxKey_Down||sym==FcitxKey_Up){
                auto *cursor=candidates->toCursorMovable();
                if(cursor){if(sym==FcitxKey_Down)cursor->nextCandidate();else cursor->prevCandidate();
                    ic->updateUserInterface(fcitx::UserInterfaceComponent::InputPanel);event.filterAndAccept();return;}
            }
        }
        unsigned vk=0;
        if(unicode>='a'&&unicode<='z')vk=unicode-'a'+'A';
        else if((unicode>='A'&&unicode<='Z')||(unicode>='0'&&unicode<='9')||unicode==' ')vk=unicode;
        else switch(sym){
        case FcitxKey_BackSpace:vk=8;break;case FcitxKey_Tab:vk=9;break;
        case FcitxKey_Return:case FcitxKey_KP_Enter:vk=13;break;
        case FcitxKey_Escape:vk=27;break;case FcitxKey_Left:vk=37;break;case FcitxKey_Right:vk=39;break;
        case FcitxKey_Home:vk=36;break;case FcitxKey_End:vk=35;break;case FcitxKey_Delete:vk=46;break;
        case FcitxKey_Shift_L:vk=160;break;case FcitxKey_Shift_R:vk=161;break;case FcitxKey_Caps_Lock:vk=20;break;
        case FcitxKey_comma:case FcitxKey_less:vk=188;break;
        case FcitxKey_period:case FcitxKey_greater:vk=190;break;
        case FcitxKey_apostrophe:case FcitxKey_quotedbl:vk=222;break;
        case FcitxKey_semicolon:case FcitxKey_colon:vk=186;break;
        case FcitxKey_slash:case FcitxKey_question:vk=191;break;
        case FcitxKey_minus:case FcitxKey_underscore:vk=189;break;
        case FcitxKey_equal:case FcitxKey_plus:vk=187;break;
        case FcitxKey_bracketleft:case FcitxKey_braceleft:vk=219;break;
        case FcitxKey_bracketright:case FcitxKey_braceright:vk=221;break;
        case FcitxKey_backslash:case FcitxKey_bar:vk=220;break;
        case FcitxKey_grave:case FcitxKey_asciitilde:vk=192;break;
        case FcitxKey_exclam:vk='1';break;case FcitxKey_at:vk='2';break;
        case FcitxKey_numbersign:vk='3';break;case FcitxKey_dollar:vk='4';break;
        case FcitxKey_percent:vk='5';break;case FcitxKey_asciicircum:vk='6';break;
        case FcitxKey_ampersand:vk='7';break;case FcitxKey_asterisk:vk='8';break;
        case FcitxKey_parenleft:vk='9';break;case FcitxKey_parenright:vk='0';break;
        default:return;
        }
        if(event.rawKey().states().test(fcitx::KeyState::Shift))vk|=0x1000;
        if(event.rawKey().states().test(fcitx::KeyState::CapsLock))vk|=0x2000;
        if(sym==FcitxKey_Caps_Lock&&!event.isRelease())vk^=0x2000;
        if(transact(ic,"K "+std::to_string(vk)+" "+(event.isRelease()?"1":"0")))event.filterAndAccept();
    }
private:
    friend class Word;
    static bool sensitive(fcitx::InputContext *ic){return !ic||ic->capabilityFlags().testAny(fcitx::CapabilityFlag::PasswordOrSensitive);}
    void clear(fcitx::InputContext *ic){generation_++;ic->inputPanel().reset();ic->updatePreedit();ic->updateUserInterface(fcitx::UserInterfaceComponent::InputPanel);}
    bool transact(fcitx::InputContext *ic,const std::string &command){
        try{
            auto reply=request(command);generation_++;
            auto &panel=ic->inputPanel();panel.reset();
            if(!reply.commit.empty()&&ic->hasFocus())ic->commitString(reply.commit);
            fcitx::Text preedit(reply.preedit,fcitx::TextFormatFlags(fcitx::TextFormatFlag::Underline)|fcitx::TextFormatFlag::DontCommit);
            preedit.setCursor(std::max(0,std::min(reply.cursor,int(reply.preedit.size()))));
            panel.setClientPreedit(preedit);panel.setPreedit(preedit);
            if(!reply.candidates.empty()){
                auto list=std::make_unique<fcitx::CommonCandidateList>();list->setPageSize(9);
                list->setLabels({"1","2","3","4","5","6","7","8","9"});
                list->setLayoutHint(fcitx::CandidateLayoutHint::Vertical);
                list->setCursorPositionAfterPaging(fcitx::CursorPositionAfterPaging::ResetToFirst);
                for(size_t i=0;i<reply.candidates.size();i++)list->append(std::make_unique<Word>(this,int(i),generation_,reply.candidates[i]));
                list->setGlobalCursorIndex(std::max(0,std::min(reply.selected,int(reply.candidates.size())-1)));
                panel.setCandidateList(std::move(list));
            }
            ic->updatePreedit();ic->updateUserInterface(fcitx::UserInterfaceComponent::InputPanel);
            return reply.result>0;
        }catch(const std::exception &){
            clear(ic);target_.unwatch();
            ic->inputPanel().setAuxUp(fcitx::Text("豆包引擎未就绪"));
            ic->updateUserInterface(fcitx::UserInterfaceComponent::InputPanel);return false;
        }
    }
    fcitx::Instance *instance_;
    fcitx::SimpleAction settingsAction_;
    fcitx::ScopedConnection settingsConnection_;
    fcitx::TrackableObjectReference<fcitx::InputContext> target_;
    unsigned generation_=0;
    std::unordered_set<unsigned> pagingKeys_;
};
void Word::select(fcitx::InputContext *ic)const{engine_->choose(ic,index_,generation_);}
class Factory:public fcitx::AddonFactory{public:fcitx::AddonInstance *create(fcitx::AddonManager *m)override{return new Engine(m->instance());}};
FCITX_ADDON_FACTORY(Factory);
