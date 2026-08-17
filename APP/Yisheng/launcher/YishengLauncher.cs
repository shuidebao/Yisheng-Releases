using System;
using System.Diagnostics;
using System.Drawing;
using System.IO;
using System.Text;
using System.Threading;
using System.Windows.Forms;

[assembly: System.Reflection.AssemblyTitle("Yisheng")]
[assembly: System.Reflection.AssemblyDescription("Free local simultaneous interpreter")]
[assembly: System.Reflection.AssemblyCompany("Huyuanhao")]
[assembly: System.Reflection.AssemblyProduct("Yisheng")]
[assembly: System.Reflection.AssemblyCopyright("Copyright © 2026 Huyuanhao")]

internal static class YishengLauncher
{
    private const string MutexName = "Local_Yisheng_Interpreter_Desktop_App";
    private const string ActivateEventName = @"Local\Yisheng_Interpreter_Activate";
    private const string QuitEventName = @"Local\Yisheng_Interpreter_Quit";

    [STAThread]
    private static void Main()
    {
        Application.EnableVisualStyles();
        Application.SetCompatibleTextRenderingDefault(false);

        bool ownsMutex;
        using (var mutex = new Mutex(true, MutexName, out ownsMutex))
        using (var activateEvent = new EventWaitHandle(false, EventResetMode.AutoReset, ActivateEventName))
        using (var quitEvent = new EventWaitHandle(false, EventResetMode.AutoReset, QuitEventName))
        {
            if (!ownsMutex)
            {
                // A second launch is an open/restore request, not an error.
                activateEvent.Set();
                return;
            }

            string root = AppDomain.CurrentDomain.BaseDirectory;
            string backend = Path.Combine(root, "runtime", "python312", "YishengBackend.exe");
            if (!File.Exists(backend))
            {
                backend = Path.Combine(root, "runtime", "python312", "pythonw.exe");
            }
            if (!File.Exists(backend))
            {
                MessageBox.Show(
                    "\u8fd0\u884c\u73af\u5883\u4e0d\u5b8c\u6574\uff0c\u8bf7\u91cd\u65b0\u8fd0\u884c\u8bd1\u58f0\u5b89\u88c5\u5305\u3002",
                    "\u8bd1\u58f0",
                    MessageBoxButtons.OK,
                    MessageBoxIcon.Warning
                );
                return;
            }

            try
            {
                using (var context = new YishengApplicationContext(root, backend, activateEvent, quitEvent))
                {
                    Application.Run(context);
                }
            }
            catch (Exception ex)
            {
                WriteLauncherError(root, ex.ToString());
                MessageBox.Show(
                    "\u8bd1\u58f0\u542f\u52a8\u5931\u8d25\uff0c\u8bf7\u67e5\u770b logs\\launcher-error.log\u3002",
                    "\u8bd1\u58f0",
                    MessageBoxButtons.OK,
                    MessageBoxIcon.Error
                );
            }
        }
    }

    internal static void WriteLauncherError(string root, string content)
    {
        string logDirectory = Path.Combine(root, "logs");
        Directory.CreateDirectory(logDirectory);
        File.WriteAllText(
            Path.Combine(logDirectory, "launcher-error.log"),
            content ?? String.Empty,
            new UTF8Encoding(false)
        );
    }
}

internal sealed class YishengApplicationContext : ApplicationContext, IDisposable
{
    private readonly string root;
    private readonly EventWaitHandle activateEvent;
    private readonly EventWaitHandle quitEvent;
    private readonly StringBuilder standardError = new StringBuilder();
    private readonly Process process;
    private readonly NotifyIcon trayIcon;
    private readonly System.Windows.Forms.Timer monitorTimer;
    private bool exitRequested;
    private DateTime forcedExitAt;
    private bool finished;

    internal YishengApplicationContext(
        string root,
        string backend,
        EventWaitHandle activateEvent,
        EventWaitHandle quitEvent)
    {
        this.root = root;
        this.activateEvent = activateEvent;
        this.quitEvent = quitEvent;

        string launcherLog = Path.Combine(root, "logs", "launcher-error.log");
        Directory.CreateDirectory(Path.GetDirectoryName(launcherLog));
        if (File.Exists(launcherLog))
        {
            File.Delete(launcherLog);
        }

        var startInfo = new ProcessStartInfo
        {
            FileName = backend,
            Arguments = "-m app.desktop",
            WorkingDirectory = root,
            UseShellExecute = false,
            CreateNoWindow = true,
            RedirectStandardError = true,
            WindowStyle = ProcessWindowStyle.Hidden
        };

        process = new Process();
        process.StartInfo = startInfo;
        process.ErrorDataReceived += delegate(object sender, DataReceivedEventArgs args)
        {
            if (args.Data != null)
            {
                lock (standardError)
                {
                    standardError.AppendLine(args.Data);
                }
            }
        };
        if (!process.Start())
        {
            throw new InvalidOperationException("Could not start the Yisheng backend.");
        }
        process.BeginErrorReadLine();

        var menu = new ContextMenuStrip();
        var openItem = new ToolStripMenuItem("\u6253\u5f00\u8bd1\u58f0");
        openItem.Font = new Font(openItem.Font, FontStyle.Bold);
        openItem.Click += delegate { RequestActivate(); };
        var exitItem = new ToolStripMenuItem("\u9000\u51fa\u8bd1\u58f0");
        exitItem.Click += delegate { RequestExit(); };
        menu.Items.Add(openItem);
        menu.Items.Add(new ToolStripSeparator());
        menu.Items.Add(exitItem);

        Icon icon = Icon.ExtractAssociatedIcon(Application.ExecutablePath);
        trayIcon = new NotifyIcon
        {
            Icon = icon ?? SystemIcons.Application,
            Text = "\u8bd1\u58f0 \u00b7 \u672c\u5730\u540c\u58f0\u4f20\u8bd1\uff08\u6b63\u5728\u8fd0\u884c\uff09",
            ContextMenuStrip = menu,
            Visible = true
        };
        trayIcon.DoubleClick += delegate { RequestActivate(); };

        monitorTimer = new System.Windows.Forms.Timer();
        monitorTimer.Interval = 250;
        monitorTimer.Tick += delegate { MonitorBackend(); };
        monitorTimer.Start();
    }

    private void RequestActivate()
    {
        activateEvent.Set();
    }

    private void RequestExit()
    {
        if (exitRequested)
        {
            return;
        }
        exitRequested = true;
        forcedExitAt = DateTime.UtcNow.AddSeconds(6);
        trayIcon.Text = "\u8bd1\u58f0\uff08\u6b63\u5728\u9000\u51fa\uff09";
        quitEvent.Set();
    }

    private void MonitorBackend()
    {
        if (finished)
        {
            return;
        }
        if (process.HasExited)
        {
            Finish();
            return;
        }
        if (exitRequested && DateTime.UtcNow >= forcedExitAt)
        {
            try
            {
                process.Kill();
            }
            catch
            {
                // The process may have completed between the checks.
            }
        }
    }

    private void Finish()
    {
        if (finished)
        {
            return;
        }
        finished = true;
        monitorTimer.Stop();
        trayIcon.Visible = false;

        int exitCode = 0;
        try
        {
            exitCode = process.ExitCode;
        }
        catch
        {
        }
        if (!exitRequested && exitCode != 0)
        {
            string error;
            lock (standardError)
            {
                error = standardError.ToString();
            }
            YishengLauncher.WriteLauncherError(root, error);
            MessageBox.Show(
                "\u8bd1\u58f0\u672a\u80fd\u6b63\u5e38\u542f\u52a8\u3002\u8bf7\u67e5\u770b logs\\desktop.log\u3002",
                "\u8bd1\u58f0",
                MessageBoxButtons.OK,
                MessageBoxIcon.Error
            );
        }
        ExitThread();
    }

    protected override void ExitThreadCore()
    {
        if (!finished && !process.HasExited)
        {
            RequestExit();
            return;
        }
        base.ExitThreadCore();
    }

    public new void Dispose()
    {
        monitorTimer.Dispose();
        trayIcon.Dispose();
        process.Dispose();
        base.Dispose();
    }
}
