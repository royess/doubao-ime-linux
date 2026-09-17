#include <windows.h>
static HANDLE output;
static int close_settings;
static void write(const char *s){DWORD n;WriteFile(output,s,lstrlenA(s),&n,0);}
static BOOL CALLBACK child(HWND hwnd,LPARAM arg){
    static WCHAR text[32000];static char utf8[96000];
    int n=GetWindowTextW(hwnd,text,32000);
    if(n){int m=WideCharToMultiByte(CP_UTF8,0,text,n,utf8,sizeof(utf8)-1,0,0);utf8[m]=0;write(utf8);write("\n");}
    return TRUE;
}
static BOOL CALLBACK window(HWND hwnd,LPARAM arg){
    if(IsWindowVisible(hwnd)){write("WINDOW\n");child(hwnd,0);EnumChildWindows(hwnd,child,0);}
    if(close_settings){WCHAR title[256];GetWindowTextW(hwnd,title,256);if(!lstrcmpW(title,L"豆包输入法设置"))PostMessageW(hwnd,WM_CLOSE,0,0);}
    return TRUE;
}
void mainCRTStartup(void){char *p=GetCommandLineA();while(*p){if(!lstrcmpA(p,"--close"))close_settings=1;p++;}output=GetStdHandle(STD_OUTPUT_HANDLE);EnumWindows(window,0);ExitProcess(0);}
