// Runs the unmodified official UI with a font available to Wine Mono WPF.
using System;
using System.IO;
using System.Reflection;
using System.Windows;
using System.Windows.Documents;
using System.Windows.Controls;
using System.Windows.Media;
using System.Windows.Threading;

class SettingsLauncher {
    static readonly FontFamily LinuxFont = new FontFamily("Noto Sans CJK SC");
    static void FixFont(DependencyObject item) {
        var text = item as TextBlock;
        if (text != null) {
            if (text.FontFamily.Source != LinuxFont.Source) text.FontFamily = LinuxFont;
            foreach (Inline inline in text.Inlines)
                if (inline.FontFamily.Source != LinuxFont.Source) inline.FontFamily = LinuxFont;
        }
        if (item is Visual) for (int i=0; i<VisualTreeHelper.GetChildrenCount(item); i++)
            FixFont(VisualTreeHelper.GetChild(item,i));
    }
    [STAThread] static int Main() {
        try {
            string dir = @"C:\DoubaoIme\versions\v0.9.0.0";
            Environment.CurrentDirectory = dir;
            Environment.SetEnvironmentVariable("windir", @"C:\windows");
            AppDomain.CurrentDomain.AssemblyResolve += (sender, args) => {
                string file = Path.Combine(dir, new AssemblyName(args.Name).Name+".dll");
                return File.Exists(file) ? Assembly.LoadFrom(file) : null;
            };
            Assembly app = Assembly.LoadFrom(Path.Combine(dir,"DoubaoImeSettings.exe"));
            var font = new FontFamily("Noto Sans CJK SC");
            EventManager.RegisterClassHandler(typeof(FrameworkElement), FrameworkElement.LoadedEvent,
                new RoutedEventHandler((sender, args) => {
                    var element = sender as FrameworkElement;
                    if (element != null) element.SetValue(TextElement.FontFamilyProperty, font);
                    var block = element as TextBlock;
                    if (block != null) foreach (Inline inline in block.Inlines) inline.FontFamily = font;
                }));
            var timer = new DispatcherTimer {Interval=TimeSpan.FromMilliseconds(750)};
            timer.Tick += (sender,args) => {
                if(Application.Current != null) foreach(Window window in Application.Current.Windows) FixFont(window);
            };
            timer.Start();
            app.EntryPoint.Invoke(null, app.EntryPoint.GetParameters().Length == 0 ? null : new object[]{new string[0]});
            return 0;
        } catch(Exception error) {
            Console.Error.WriteLine(error);
            return 1;
        }
    }
}
