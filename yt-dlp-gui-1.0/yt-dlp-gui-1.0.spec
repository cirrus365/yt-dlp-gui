Name:           yt-dlp-gui
Version:        1.0
Release:        1%{?dist}
Summary:        PyQt5 wrapper for yt-dlp
License:        MIT
Source0:        %{name}-%{version}.tar.gz
Requires:       python3-PyQt5 yt-dlp ffmpeg-free

BuildArch:      noarch

%description
A PyQt5 wrapper for yt-dlp.

%prep
%setup -q

%install
mkdir -p %{buildroot}%{_bindir}
mkdir -p %{buildroot}%{_datadir}/applications
mkdir -p %{buildroot}%{_datadir}/icons/hicolor/scalable/apps

install -m 755 yt-dlp-gui.py %{buildroot}%{_bindir}/yt-dlp-gui-1.0
install -m 644 yt-dlp-gui.svg %{buildroot}%{_datadir}/icons/hicolor/scalable/apps/yt-dlp-gui-1.0.svg
install -m 644 yt-dlp-gui.desktop %{buildroot}%{_datadir}/applications/yt-dlp-gui-1.0.desktop

%files
%{_bindir}/yt-dlp-gui-1.0
%{_datadir}/applications/yt-dlp-gui-1.0.desktop
%{_datadir}/icons/hicolor/scalable/apps/yt-dlp-gui-1.0.svg

