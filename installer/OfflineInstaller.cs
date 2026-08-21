using System;
using System.Collections.Generic;
using System.ComponentModel;
using System.Diagnostics;
using System.Drawing;
using System.IO;
using System.IO.Compression;
using System.Reflection;
using System.Security.Cryptography;
using System.Text;
using System.Threading;
using System.Runtime.InteropServices;
using System.Windows.Forms;

[assembly: AssemblyTitle("Yisheng Offline Installer")]
[assembly: AssemblyDescription("Offline installer for Yisheng")]
[assembly: AssemblyCompany("Huyuanhao")]
[assembly: AssemblyProduct("Yisheng")]
[assembly: AssemblyCopyright("Copyright © 2026 Huyuanhao")]

internal sealed class PackageInfo
{
    internal long Offset;
    internal long Length;
    internal byte[] Sha256;
}

internal sealed class InstallResult
{
    internal string Target;
    internal string ShortcutWarning;
}

[StructLayout(LayoutKind.Sequential, CharSet = CharSet.Auto)]
internal sealed class MemoryStatusEx
{
    internal uint Length = (uint)Marshal.SizeOf(typeof(MemoryStatusEx));
    internal uint MemoryLoad;
    internal ulong TotalPhysical;
    internal ulong AvailablePhysical;
    internal ulong TotalPageFile;
    internal ulong AvailablePageFile;
    internal ulong TotalVirtual;
    internal ulong AvailableVirtual;
    internal ulong AvailableExtendedVirtual;
}

internal sealed class InstallerForm : Form
{
    private const string InstallerVersion = BuildInfo.Version;
    private const long Megabyte = 1024L * 1024L;
    private const long Gigabyte = 1024L * 1024L * 1024L;
    private const long InstalledSpaceRequired = 1000L * Megabyte;
    private readonly TextBox pathBox = new TextBox();
    private readonly Button browseButton = new Button();
    private readonly Button installButton = new Button();
    private readonly ProgressBar progressBar = new ProgressBar();
    private readonly Label statusLabel = new Label();
    private readonly CheckBox launchCheck = new CheckBox();
    private readonly BackgroundWorker worker = new BackgroundWorker();

    internal InstallerForm(string initialPath = null)
    {
        Text = "译声 YiSheng " + InstallerVersion + " Offline Installer";
        ClientSize = new Size(790, 500);
        MinimumSize = new Size(720, 470);
        StartPosition = FormStartPosition.CenterScreen;
        BackColor = Color.FromArgb(12, 15, 22);
        ForeColor = Color.WhiteSmoke;
        Font = new Font("Microsoft YaHei UI", 10F);
        FormBorderStyle = FormBorderStyle.FixedSingle;
        MaximizeBox = false;

        Label title = new Label();
        title.Text = "译声 YiSheng · 本地同声传译";
        title.Font = new Font("Microsoft YaHei UI", 21F, FontStyle.Bold);
        title.ForeColor = Color.FromArgb(205, 255, 65);
        title.AutoSize = true;
        title.Location = new Point(38, 32);
        Controls.Add(title);

        Label version = new Label();
        version.Text = "版本 / Version " + InstallerVersion + "  |  Windows 10/11 64-bit  |  离线 / Offline";
        version.AutoSize = true;
        version.ForeColor = Color.Gainsboro;
        version.Location = new Point(42, 82);
        Controls.Add(version);

        Label description = new Label();
        description.Text = "已包含 Base 语音识别和中 / 日 / 英互译模型，无需另外下载。\r\nIncludes Base speech recognition and offline Chinese / Japanese / English translation models.";
        description.AutoSize = true;
        description.MaximumSize = new Size(705, 55);
        description.ForeColor = Color.Silver;
        description.Location = new Point(42, 122);
        Controls.Add(description);

        Label pathLabel = new Label();
        pathLabel.Text = "安装位置 / Install location";
        pathLabel.AutoSize = true;
        pathLabel.Font = new Font(Font, FontStyle.Bold);
        pathLabel.Location = new Point(42, 186);
        Controls.Add(pathLabel);

        pathBox.Location = new Point(45, 216);
        pathBox.Size = new Size(575, 30);
        pathBox.Text = String.IsNullOrWhiteSpace(initialPath)
            ? Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "Yisheng")
            : initialPath;
        pathBox.BackColor = Color.FromArgb(28, 34, 48);
        pathBox.ForeColor = Color.White;
        pathBox.BorderStyle = BorderStyle.FixedSingle;
        Controls.Add(pathBox);

        browseButton.Text = "浏览 / Browse…";
        browseButton.Location = new Point(630, 213);
        browseButton.Size = new Size(120, 36);
        browseButton.Click += BrowseClicked;
        Controls.Add(browseButton);

        Label hint = new Label();
        hint.Text = "至少 4 GB 内存和约 1.6 GB 磁盘空间 / Requires 4 GB RAM and about 1.6 GB free disk space.";
        hint.AutoSize = true;
        hint.MaximumSize = new Size(705, 42);
        hint.ForeColor = Color.Gray;
        hint.Location = new Point(43, 258);
        Controls.Add(hint);

        progressBar.Location = new Point(45, 306);
        progressBar.Size = new Size(705, 23);
        progressBar.Style = ProgressBarStyle.Continuous;
        Controls.Add(progressBar);

        statusLabel.Text = "准备安装 / Ready to install.";
        statusLabel.Location = new Point(43, 340);
        statusLabel.Size = new Size(707, 45);
        statusLabel.ForeColor = Color.LightGray;
        Controls.Add(statusLabel);

        launchCheck.Text = "安装完成后启动译声 / Launch YiSheng after installation";
        launchCheck.Checked = true;
        launchCheck.AutoSize = true;
        launchCheck.Location = new Point(45, 412);
        Controls.Add(launchCheck);

        installButton.Text = String.IsNullOrWhiteSpace(initialPath) ? "安装 / Install" : "更新 / Update";
        installButton.BackColor = Color.FromArgb(205, 255, 65);
        installButton.ForeColor = Color.FromArgb(15, 18, 24);
        installButton.FlatStyle = FlatStyle.Flat;
        installButton.Font = new Font(Font, FontStyle.Bold);
        installButton.Location = new Point(580, 398);
        installButton.Size = new Size(170, 52);
        installButton.Click += InstallClicked;
        Controls.Add(installButton);

        worker.WorkerReportsProgress = true;
        worker.DoWork += InstallInBackground;
        worker.ProgressChanged += WorkerProgressChanged;
        worker.RunWorkerCompleted += WorkerCompleted;
    }

    private void BrowseClicked(object sender, EventArgs e)
    {
        using (FolderBrowserDialog dialog = new FolderBrowserDialog())
        {
            dialog.Description = "选择译声安装文件夹";
            dialog.SelectedPath = Directory.Exists(pathBox.Text) ? pathBox.Text : Path.GetPathRoot(pathBox.Text);
            if (dialog.ShowDialog(this) == DialogResult.OK)
            {
                pathBox.Text = dialog.SelectedPath.TrimEnd(Path.DirectorySeparatorChar) + Path.DirectorySeparatorChar + "Yisheng";
            }
        }
    }

    private void InstallClicked(object sender, EventArgs e)
    {
        string target;
        try
        {
            target = ValidateInstallPath(pathBox.Text);
        }
        catch (Exception ex)
        {
            MessageBox.Show(this, ex.Message, "安装位置不可用", MessageBoxButtons.OK, MessageBoxIcon.Warning);
            return;
        }

        pathBox.Text = target;
        SetControlsEnabled(false);
        progressBar.Value = 0;
        statusLabel.Text = "正在读取离线安装数据…";
        worker.RunWorkerAsync(target);
    }

    private static string ValidateInstallPath(string value)
    {
        if (String.IsNullOrWhiteSpace(value)) throw new InvalidOperationException("请选择安装位置。");
        string full = Path.GetFullPath(Environment.ExpandEnvironmentVariables(value.Trim().Trim('"')));
        string root = Path.GetPathRoot(full);
        if (String.Equals(full.TrimEnd(Path.DirectorySeparatorChar), root.TrimEnd(Path.DirectorySeparatorChar), StringComparison.OrdinalIgnoreCase))
            throw new InvalidOperationException("不能直接安装到磁盘根目录，请选择一个文件夹，例如 D:\\Yisheng。");
        if (full.Length > 90)
            throw new InvalidOperationException("安装路径过长，请选择较短的位置，例如 D:\\Yisheng。这样可以避免 Windows 文件路径限制导致安装失败。");
        Directory.CreateDirectory(full);
        string probe = Path.Combine(full, ".yisheng-write-test");
        File.WriteAllText(probe, "ok", Encoding.ASCII);
        File.Delete(probe);
        return full;
    }

    private void SetControlsEnabled(bool enabled)
    {
        pathBox.Enabled = enabled;
        browseButton.Enabled = enabled;
        installButton.Enabled = enabled;
    }

    private void InstallInBackground(object sender, DoWorkEventArgs e)
    {
        string target = (string)e.Argument;
        string shortcutWarning = InstallPackage(target, delegate(int percent, string text) { worker.ReportProgress(percent, text); }, true);
        e.Result = new InstallResult { Target = target, ShortcutWarning = shortcutWarning };
    }

    private void WorkerProgressChanged(object sender, ProgressChangedEventArgs e)
    {
        progressBar.Value = Math.Max(0, Math.Min(100, e.ProgressPercentage));
        statusLabel.Text = Convert.ToString(e.UserState);
    }

    private void WorkerCompleted(object sender, RunWorkerCompletedEventArgs e)
    {
        if (e.Error != null)
        {
            SetControlsEnabled(true);
            statusLabel.Text = "安装失败：" + e.Error.Message;
            statusLabel.ForeColor = Color.FromArgb(255, 105, 105);
            WriteErrorLog(e.Error);
            MessageBox.Show(this, "安装没有完成。\r\n\r\n" + e.Error.Message + "\r\n\r\n错误记录已保存到安装包旁边的 Yisheng-install-error.log。", "译声安装失败", MessageBoxButtons.OK, MessageBoxIcon.Error);
            return;
        }

        InstallResult result = (InstallResult)e.Result;
        string target = result.Target;
        progressBar.Value = 100;
        statusLabel.ForeColor = Color.FromArgb(205, 255, 65);
        statusLabel.Text = String.IsNullOrEmpty(result.ShortcutWarning)
            ? "安装完成。桌面和开始菜单快捷方式已经创建。"
            : "安装完成，但部分快捷方式未能创建。可直接运行安装目录中的 Yisheng.exe。";
        installButton.Text = "完成";
        installButton.Enabled = true;
        installButton.Click -= InstallClicked;
        installButton.Click += delegate { Close(); };

        if (launchCheck.Checked)
        {
            try
            {
                string executable = Path.Combine(target, "Yisheng.exe");
                if (!File.Exists(executable)) throw new FileNotFoundException("安装后的启动文件不存在。", executable);
                Process.Start(new ProcessStartInfo {
                    FileName = executable,
                    WorkingDirectory = target,
                    UseShellExecute = false
                });
            }
            catch (Exception ex)
            {
                statusLabel.Text = "应用已安装完成，但自动启动失败。请从安装目录运行 Yisheng.exe。";
                WriteErrorLog(new IOException("应用已安装完成，但自动启动失败。", ex));
                MessageBox.Show(this, "译声已经安装完成，但自动启动失败。\r\n\r\n请从安装目录运行：\r\n" + Path.Combine(target, "Yisheng.exe"), "译声启动失败", MessageBoxButtons.OK, MessageBoxIcon.Warning);
            }
        }
    }

    private static void WriteErrorLog(Exception error)
    {
        try
        {
            string besideInstaller = Path.Combine(AppDomain.CurrentDomain.BaseDirectory, "Yisheng-install-error.log");
            File.WriteAllText(besideInstaller, DateTime.Now.ToString("s") + Environment.NewLine + error, new UTF8Encoding(false));
        }
        catch { }
    }

    internal static string InstallPackage(string target, Action<int, string> report, bool createShortcuts)
    {
        PackageInfo info = ReadPackageInfo(Application.ExecutablePath);
        CheckComputerResources(target, info);
        string tempZip = Path.Combine(Path.GetTempPath(), "Yisheng-" + Guid.NewGuid().ToString("N") + ".zip");
        try
        {
            report(1, "正在验证离线安装数据…");
            CopyAndVerifyPackage(Application.ExecutablePath, info, tempZip, report);
            ExtractPackage(tempZip, target, report);
            RemoveObsoleteComponents(target);
            VerifyInstallation(target);
            string shortcutWarning = createShortcuts ? CreateShortcuts(target) : null;
            report(100, "安装完成。");
            return shortcutWarning;
        }
        finally
        {
            try { if (File.Exists(tempZip)) File.Delete(tempZip); }
            catch { }
        }
    }

    [DllImport("kernel32.dll", CharSet = CharSet.Auto, SetLastError = true)]
    private static extern bool GlobalMemoryStatusEx([In, Out] MemoryStatusEx status);

    private static void CheckComputerResources(string target, PackageInfo info)
    {
        MemoryStatusEx memory = new MemoryStatusEx();
        if (GlobalMemoryStatusEx(memory))
        {
            double totalGb = memory.TotalPhysical / (double)Gigabyte;
            double availableGb = memory.AvailablePhysical / (double)Gigabyte;
            if (totalGb < 3.5)
                throw new InvalidOperationException("运行内存不足：本机共有 " + totalGb.ToString("0.0") + " GB，译声 Base 模型至少需要 4 GB 运行内存。");
            if (availableGb < 0.75)
                throw new InvalidOperationException("当前可用运行内存不足：仅剩 " + availableGb.ToString("0.0") + " GB。请关闭游戏、浏览器等程序后重试。");
        }

        string targetRoot = Path.GetPathRoot(Path.GetFullPath(target));
        string tempRoot = Path.GetPathRoot(Path.GetFullPath(Path.GetTempPath()));
        DriveInfo targetDrive = new DriveInfo(targetRoot);
        DriveInfo tempDrive = new DriveInfo(tempRoot);
        long tempRequired = info.Length + 128L * Megabyte;

        if (String.Equals(targetRoot, tempRoot, StringComparison.OrdinalIgnoreCase))
        {
            long required = InstalledSpaceRequired + tempRequired;
            if (targetDrive.AvailableFreeSpace < required)
                throw new IOException("磁盘空间不足：安装盘还需要约 " + ((required - targetDrive.AvailableFreeSpace + Megabyte - 1) / Megabyte) + " MB 可用空间。请选择其他磁盘或先清理空间。");
        }
        else
        {
            if (tempDrive.AvailableFreeSpace < tempRequired)
                throw new IOException("系统临时盘空间不足：C 盘还需要约 " + ((tempRequired - tempDrive.AvailableFreeSpace + Megabyte - 1) / Megabyte) + " MB。请先清理 C 盘后重试。");
            if (targetDrive.AvailableFreeSpace < InstalledSpaceRequired)
                throw new IOException("安装位置磁盘空间不足：还需要约 " + ((InstalledSpaceRequired - targetDrive.AvailableFreeSpace + Megabyte - 1) / Megabyte) + " MB。请选择其他磁盘或先清理空间。");
        }
    }

    private static PackageInfo ReadPackageInfo(string executable)
    {
        const int FooterSize = 56;
        byte[] expectedMagic = Encoding.ASCII.GetBytes("YSHZIP01");
        using (FileStream stream = File.OpenRead(executable))
        {
            if (stream.Length < FooterSize) throw new InvalidDataException("安装包数据不完整，请重新下载。 ");
            stream.Seek(-FooterSize, SeekOrigin.End);
            using (BinaryReader reader = new BinaryReader(stream, Encoding.UTF8, true))
            {
                byte[] magic = reader.ReadBytes(8);
                if (!FixedEquals(magic, expectedMagic)) throw new InvalidDataException("没有找到离线安装数据，请重新下载安装包。");
                PackageInfo info = new PackageInfo();
                info.Offset = reader.ReadInt64();
                info.Length = reader.ReadInt64();
                info.Sha256 = reader.ReadBytes(32);
                if (info.Offset < 0 || info.Length <= 0 || info.Offset + info.Length + FooterSize != stream.Length)
                    throw new InvalidDataException("安装包大小校验失败，请重新下载。");
                return info;
            }
        }
    }

    private static bool FixedEquals(byte[] left, byte[] right)
    {
        if (left == null || right == null || left.Length != right.Length) return false;
        int difference = 0;
        for (int i = 0; i < left.Length; i++) difference |= left[i] ^ right[i];
        return difference == 0;
    }

    private static void CopyAndVerifyPackage(string executable, PackageInfo info, string tempZip, Action<int, string> report)
    {
        byte[] buffer = new byte[1024 * 1024];
        long copied = 0;
        using (FileStream input = File.OpenRead(executable))
        using (FileStream output = new FileStream(tempZip, FileMode.CreateNew, FileAccess.Write, FileShare.None))
        using (SHA256 hash = SHA256.Create())
        {
            input.Position = info.Offset;
            int lastPercent = 0;
            while (copied < info.Length)
            {
                int wanted = (int)Math.Min(buffer.Length, info.Length - copied);
                int read = input.Read(buffer, 0, wanted);
                if (read <= 0) throw new EndOfStreamException("安装包下载不完整，请重新下载。");
                output.Write(buffer, 0, read);
                hash.TransformBlock(buffer, 0, read, null, 0);
                copied += read;
                int percent = 1 + (int)(copied * 14L / info.Length);
                if (percent != lastPercent)
                {
                    report(percent, "正在验证离线安装数据… " + (copied / 1024 / 1024) + " / " + (info.Length / 1024 / 1024) + " MB");
                    lastPercent = percent;
                }
            }
            hash.TransformFinalBlock(new byte[0], 0, 0);
            if (!FixedEquals(hash.Hash, info.Sha256)) throw new InvalidDataException("安装包校验失败，文件可能没有下载完整，请重新下载。");
        }
    }

    private static void ExtractPackage(string zipPath, string target, Action<int, string> report)
    {
        string root = Path.GetFullPath(target).TrimEnd(Path.DirectorySeparatorChar) + Path.DirectorySeparatorChar;
        Directory.CreateDirectory(root);
        using (FileStream stream = File.OpenRead(zipPath))
        using (ZipArchive archive = new ZipArchive(stream, ZipArchiveMode.Read))
        {
            long total = 0;
            foreach (ZipArchiveEntry entry in archive.Entries) total += Math.Max(0, entry.Length);
            if (total <= 0) throw new InvalidDataException("离线安装数据为空。");

            DriveInfo drive = new DriveInfo(Path.GetPathRoot(root));
            if (drive.AvailableFreeSpace < total + 300L * 1024L * 1024L)
                throw new IOException("磁盘空间不足，请至少再释放 " + ((total + 300L * 1024L * 1024L - drive.AvailableFreeSpace) / 1024 / 1024) + " MB。");

            long done = 0;
            byte[] buffer = new byte[1024 * 1024];
            int lastPercent = 14;
            foreach (ZipArchiveEntry entry in archive.Entries)
            {
                string relative = entry.FullName.Replace('/', Path.DirectorySeparatorChar).TrimStart(Path.DirectorySeparatorChar);
                if (String.IsNullOrEmpty(relative)) continue;
                string destination = Path.GetFullPath(Path.Combine(root, relative));
                if (!destination.StartsWith(root, StringComparison.OrdinalIgnoreCase)) throw new InvalidDataException("安装包中包含不安全的文件路径。");

                if (entry.FullName.EndsWith("/", StringComparison.Ordinal))
                {
                    Directory.CreateDirectory(destination);
                    continue;
                }

                string parent = Path.GetDirectoryName(destination);
                if (!String.IsNullOrEmpty(parent)) Directory.CreateDirectory(parent);
                using (Stream input = entry.Open())
                using (FileStream output = new FileStream(destination, FileMode.Create, FileAccess.Write, FileShare.None))
                {
                    int read;
                    while ((read = input.Read(buffer, 0, buffer.Length)) > 0)
                    {
                        output.Write(buffer, 0, read);
                        done += read;
                        int percent = 15 + (int)(done * 82L / total);
                        if (percent != lastPercent)
                        {
                            report(percent, "正在安装离线组件… " + (done / 1024 / 1024) + " / " + (total / 1024 / 1024) + " MB");
                            lastPercent = percent;
                        }
                    }
                }
            }
        }
    }

    private static void VerifyInstallation(string target)
    {
        string[] required = new string[] {
            "Yisheng.exe",
            Path.Combine("runtime", "python312", "pythonw.exe"),
            Path.Combine("runtime", "python312", "Lib", "site-packages", "faster_whisper", "__init__.py"),
            Path.Combine(".models", "whisper", "local", "base", "model.bin"),
            Path.Combine(".models", "argos", "translate-en_zh-1_9", "model", "model.bin"),
            Path.Combine(".models", "argos", "translate-zh_en-1_9", "model", "model.bin"),
            Path.Combine(".models", "argos", "en_ja", "model", "model.bin"),
            Path.Combine(".models", "translations", "ja_en", "model.bin"),
            Path.Combine("app", "main.py"),
            Path.Combine("static", "index.html")
        };
        foreach (string relative in required)
        {
            string path = Path.Combine(target, relative);
            if (!File.Exists(path) || new FileInfo(path).Length == 0) throw new InvalidDataException("安装验证失败，缺少文件：" + relative);
        }
    }

    private static void RemoveObsoleteComponents(string target)
    {
        string root = Path.GetFullPath(target).TrimEnd(Path.DirectorySeparatorChar) + Path.DirectorySeparatorChar;
        string[] obsolete = new string[] {
            Path.Combine(".models", "argos", "ja_en"),
            Path.Combine(".models", "argos", "translate-ja_en-1_1"),
            Path.Combine("runtime", "python312", "Lib", "site-packages", "torch"),
            Path.Combine("runtime", "python312", "Lib", "site-packages", "stanza"),
            Path.Combine("runtime", "python312", "Lib", "site-packages", "spacy"),
            Path.Combine("runtime", "python312", "Lib", "site-packages", "argostranslate"),
            Path.Combine("runtime", "python312", "Lib", "site-packages", "sympy"),
            Path.Combine("runtime", "python312", "Lib", "site-packages", "networkx"),
            Path.Combine("runtime", "python312", "Lib", "site-packages", "torchgen"),
            Path.Combine("runtime", "python312", "Lib", "site-packages", "mpmath"),
            Path.Combine("runtime", "python312", "Lib", "site-packages", "blis"),
            Path.Combine("runtime", "python312", "Lib", "site-packages", "thinc"),
            Path.Combine("runtime", "python312", "Lib", "site-packages", "srsly"),
            Path.Combine("runtime", "python312", "Lib", "site-packages", "emoji"),
            Path.Combine("runtime", "python312", "Lib", "site-packages", "sacremoses"),
            Path.Combine("runtime", "python312", "Lib", "site-packages", "hf_xet")
        };
        foreach (string relative in obsolete)
        {
            string path = Path.GetFullPath(Path.Combine(root, relative));
            if (path.StartsWith(root, StringComparison.OrdinalIgnoreCase) && Directory.Exists(path))
            {
                try { Directory.Delete(path, true); }
                catch { }
            }
        }

        string sitePackages = Path.Combine(root, "runtime", "python312", "Lib", "site-packages");
        string[] obsoleteMetadata = new string[] {
            "torch-*.dist-info", "stanza-*.dist-info", "spacy-*.dist-info",
            "argostranslate-*.dist-info", "sympy-*.dist-info", "networkx-*.dist-info",
            "mpmath-*.dist-info", "blis-*.dist-info", "thinc-*.dist-info",
            "srsly-*.dist-info", "emoji-*.dist-info", "sacremoses-*.dist-info",
            "hf_xet-*.dist-info"
        };
        if (Directory.Exists(sitePackages))
        {
            foreach (string pattern in obsoleteMetadata)
            {
                foreach (string path in Directory.GetDirectories(sitePackages, pattern, SearchOption.TopDirectoryOnly))
                {
                    if (!Path.GetFullPath(path).StartsWith(root, StringComparison.OrdinalIgnoreCase)) continue;
                    try { Directory.Delete(path, true); }
                    catch { }
                }
            }
        }
    }

    private static string CreateShortcuts(string target)
    {
        string executable = Path.Combine(target, "Yisheng.exe");
        List<string> warnings = new List<string>();

        TryCreateShortcut(
            Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.DesktopDirectory), "Yisheng.lnk"),
            executable,
            target,
            "桌面",
            warnings);

        // Keep the directory name ASCII-safe. WScript.Shell can convert a non-ASCII
        // shortcut path to "??" on Windows installations using a non-CJK system locale.
        string menu = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.Programs), "Yisheng");
        try
        {
            Directory.CreateDirectory(menu);
            TryCreateShortcut(Path.Combine(menu, "Yisheng.lnk"), executable, target, "开始菜单", warnings);
        }
        catch (Exception ex)
        {
            warnings.Add("开始菜单快捷方式：" + DescribeException(ex));
        }

        if (warnings.Count == 0) return null;
        string warning = String.Join(Environment.NewLine, warnings.ToArray());
        WriteErrorLog(new IOException("应用文件已安装完成，但部分快捷方式创建失败。" + Environment.NewLine + warning));
        return warning;
    }

    private static void TryCreateShortcut(string shortcutPath, string executable, string workingDirectory, string label, List<string> warnings)
    {
        try
        {
            CreateShortcut(shortcutPath, executable, workingDirectory);
        }
        catch (Exception ex)
        {
            warnings.Add(label + "快捷方式：" + DescribeException(ex));
        }
    }

    private static string DescribeException(Exception error)
    {
        Exception current = error;
        while (current.InnerException != null) current = current.InnerException;
        return current.GetType().Name + ": " + current.Message;
    }

    private static void CreateShortcut(string shortcutPath, string executable, string workingDirectory)
    {
        Type shellType = Type.GetTypeFromProgID("WScript.Shell");
        if (shellType == null) throw new InvalidOperationException("Windows Script Host 不可用。");
        object shell = Activator.CreateInstance(shellType);
        object shortcut = null;
        try
        {
            shortcut = shellType.InvokeMember("CreateShortcut", BindingFlags.InvokeMethod, null, shell, new object[] { shortcutPath });
            Type shortcutType = shortcut.GetType();
            shortcutType.InvokeMember("TargetPath", BindingFlags.SetProperty, null, shortcut, new object[] { executable });
            shortcutType.InvokeMember("WorkingDirectory", BindingFlags.SetProperty, null, shortcut, new object[] { workingDirectory });
            shortcutType.InvokeMember("IconLocation", BindingFlags.SetProperty, null, shortcut, new object[] { executable + ",0" });
            shortcutType.InvokeMember("Description", BindingFlags.SetProperty, null, shortcut, new object[] { "译声 · 免费本地同声传译" });
            shortcutType.InvokeMember("Save", BindingFlags.InvokeMethod, null, shortcut, null);
        }
        finally
        {
            if (shortcut != null && System.Runtime.InteropServices.Marshal.IsComObject(shortcut)) System.Runtime.InteropServices.Marshal.FinalReleaseComObject(shortcut);
            if (shell != null && System.Runtime.InteropServices.Marshal.IsComObject(shell)) System.Runtime.InteropServices.Marshal.FinalReleaseComObject(shell);
        }
    }
}

internal static class Program
{
    [STAThread]
    private static int Main(string[] args)
    {
        if (args.Length >= 2 && String.Equals(args[0], "--extract-only", StringComparison.OrdinalIgnoreCase))
        {
            try
            {
                string target = Path.GetFullPath(args[1]);
                InstallerForm.InstallPackage(target, delegate(int percent, string text) { Console.WriteLine(percent + "% " + text); }, false);
                Console.WriteLine("安装验证通过：" + target);
                return 0;
            }
            catch (Exception ex)
            {
                Console.Error.WriteLine(ex);
                return 1;
            }
        }

        Application.EnableVisualStyles();
        Application.SetCompatibleTextRenderingDefault(false);
        string upgradePath = null;
        if (args.Length >= 2 && String.Equals(args[0], "--upgrade", StringComparison.OrdinalIgnoreCase))
            upgradePath = args[1];
        Application.Run(new InstallerForm(upgradePath));
        return 0;
    }
}
