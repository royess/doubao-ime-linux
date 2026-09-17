#include <windows.h>
typedef void (*Ensure)(void);
typedef void (*Focus)(const char *,const char *);
typedef void (*One)(const char *);
typedef void (*Show)(const char *,int);
typedef int (*Down)(const char *,unsigned int,UINT_PTR,const char *);
typedef int (*Up)(const char *,unsigned int);
typedef int (*Comp)(const char *,char *,int,int *);
typedef int (*Commit)(const char *,char *,int);
typedef int (*Candidates)(const char *,char *,int,int *,int *,int *);
static const char *endpoint="\\\\.\\pipe\\ObricIme\\oime-server";
static HANDLE input,output;
static char preedit[65536],candidates[65536],commit[65536],line[256],number[256];
static Down down;static Up up;static Comp getcomp;static Commit getcommit;static Candidates getcands;
static int selected,previous,next,cursor,candidate_size;
static void write(const char *s){DWORD n;WriteFile(output,s,lstrlenA(s),&n,0);}
static void quoted(const char *s){
    write("\"");
    for(int i=0;s[i];i++){
        char b[8];unsigned char c=s[i];
        if(c=='\"'||c=='\\'){b[0]='\\';b[1]=c;b[2]=0;write(b);}
        else if(c<32){wsprintfA(b,"\\u%04x",c);write(b);}
        else {b[0]=c;b[1]=0;write(b);}
    }
    write("\"");
}
static unsigned parse(char **p){unsigned n=0;while(**p==' ')(*p)++;while(**p>='0'&&**p<='9'){n=n*10+**p-'0';(*p)++;}return n;}
static int key(unsigned vk){
    // Official TSF helper RVA 0x7c10 packs modifier bits into the key code.
    // Arguments 3/4 are timestamp in microseconds and host application name.
    return down(endpoint,vk,GetTickCount64()*1000,"fcitx5-doubao.exe");
}
static void snapshot(void){
    preedit[0]=candidates[0]=commit[0]=0;cursor=selected=previous=next=0;
    getcomp(endpoint,preedit,sizeof(preedit),&cursor);
    candidate_size=getcands(endpoint,candidates,sizeof(candidates),&selected,&previous,&next);
    getcommit(endpoint,commit,sizeof(commit));
}
static void report(int result){
    wsprintfA(number,"{\"result\":%d,\"cursor\":%d,\"selected\":%d,\"has_prev\":%d,\"has_next\":%d,\"preedit\":",result,cursor,selected,previous,next);
    write(number);quoted(preedit);write(",\"candidates\":");quoted(candidates);write(",\"commit\":");quoted(commit);write("}\n");
}
void mainCRTStartup(void){
    input=GetStdHandle(STD_INPUT_HANDLE);output=GetStdHandle(STD_OUTPUT_HANDLE);
    SetErrorMode(SEM_FAILCRITICALERRORS|SEM_NOGPFAULTERRORBOX);
    SetCurrentDirectoryW(L"C:\\DoubaoIme\\versions\\v0.9.0.0");
    SetDllDirectoryW(L"C:\\DoubaoIme\\versions\\v0.9.0.0");
    HMODULE dll=LoadLibraryW(L"C:\\DoubaoIme\\versions\\v0.9.0.0\\rpc.dll");
    if(!dll)ExitProcess(2);
#define LOAD(type,var,name) type var=(type)GetProcAddress(dll,name);if(!var)ExitProcess(3)
    LOAD(Ensure,ensure,"RpcPipe_EnsureServerRunning");
    LOAD(Focus,focus,"RpcPipe_FocusIn");LOAD(One,out,"RpcPipe_FocusOut");
    LOAD(Show,show,"RpcPipe_SetUIElementShowState");
    down=(Down)GetProcAddress(dll,"RpcPipe_KeyDown");up=(Up)GetProcAddress(dll,"RpcPipe_KeyUp");
    getcomp=(Comp)GetProcAddress(dll,"RpcPipe_GetCompTextUtf8");getcommit=(Commit)GetProcAddress(dll,"RpcPipe_GetCommitTextUtf8");
    getcands=(Candidates)GetProcAddress(dll,"RpcPipe_GetCandidateListUtf8");
    if(!down||!up||!getcomp||!getcommit||!getcands)ExitProcess(3);
    ensure();
    for(int i=0;i<150;i++){if(WaitNamedPipeA(endpoint,100))break;Sleep(100);}
    focus(endpoint,"fcitx5-doubao");show(endpoint,0);key(VK_ESCAPE);snapshot();
    write("{\"ready\":true}\n");
    for(;;){
        DWORD n;int length=0;
        while(length<255){if(!ReadFile(input,line+length,1,&n,0)||!n){out(endpoint);ExitProcess(0);}if(line[length]=='\n')break;length++;}
        line[length]=0;int result=0;char *p=line+1;
        if(line[0]=='F'){key(VK_ESCAPE);out(endpoint);focus(endpoint,"fcitx5-doubao");show(endpoint,0);}
        else if(line[0]=='R'){key(VK_ESCAPE);out(endpoint);}
        else if(line[0]=='K'){
            unsigned vk=parse(&p),release=parse(&p);
            result=release?up(endpoint,vk):key(vk);
        }else if(line[0]=='S'){
            unsigned target=parse(&p);snapshot();
            int attempts=0;
            while(selected!=(int)target&&attempts++<64){
                int old=selected;key(selected<(int)target?VK_DOWN:VK_UP);snapshot();
                if(selected==old)break;
            }
            result=selected==(int)target?key(VK_SPACE):-2;
        }else if(line[0]=='Q'){out(endpoint);ExitProcess(0);}
        else result=-3;
        snapshot();report(result);
    }
}
