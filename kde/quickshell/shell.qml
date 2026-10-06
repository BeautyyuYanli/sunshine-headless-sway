pragma ComponentBehavior: Bound
// Private-session shell. Start through Sway so IPC, Wayland and PipeWire all
// refer to the streaming desktop. Never import this environment into systemd.
import QtQuick
import QtQuick.Layouts
import Quickshell
import Quickshell.Io
import Quickshell.I3
import Quickshell.Wayland
import Quickshell.Services.Pipewire

ShellRoot {
    id: root
    property bool revealed: false
    property var restoreFullscreen: []

    // Sway refuses to focus a sibling hidden by a fullscreen container.
    // Returning to the window restores its previous fullscreen state.
    function activateWindow(window): void {
        if (root.activeWindow && root.activeWindow !== window && root.activeWindow.fullscreen) {
            root.restoreFullscreen = root.restoreFullscreen.filter(w => w !== null && w !== root.activeWindow).concat([root.activeWindow]);
            root.activeWindow.fullscreen = false;
        }
        window.activate();
    }
    readonly property var activeWindow: ToplevelManager.activeToplevel
    readonly property bool fullscreen: activeWindow ? activeWindow.fullscreen : false
    readonly property var sink: Pipewire.defaultAudioSink
    readonly property var audio: sink ? sink.audio : null

    SystemClock {
        id: clock
        precision: SystemClock.Minutes
    }
    PwObjectTracker {
        objects: root.sink ? [root.sink] : []
    }
    IpcHandler {
        target: "shell"
        function toggle(): void {
            root.revealed = !root.revealed;
        }
    }
    // Revealing is temporary: switching applications returns to normal policy.
    Connections {
        target: ToplevelManager
        function onActiveToplevelChanged() {
            // Let active-window bindings settle before updating fullscreen and visibility.
            Qt.callLater(() => {
                const window = ToplevelManager.activeToplevel;
                if (window && root.restoreFullscreen.indexOf(window) !== -1) {
                    root.restoreFullscreen = root.restoreFullscreen.filter(w => w !== null && w !== window);
                    window.fullscreen = true;
                }
                root.revealed = false;
            });
        }
    }

    Variants {
        model: Quickshell.screens
        Scope {
            id: desktop
            required property var modelData

            // Quickshell supplies a platform-specific PanelWindow at runtime.
            // qmllint disable uncreatable-type
            PanelWindow {
                // qmllint enable uncreatable-type
                id: top
                screen: desktop.modelData
                visible: !root.fullscreen || root.revealed
                anchors {
                    top: true
                    left: true
                    right: true
                }
                implicitHeight: 46
                exclusiveZone: root.fullscreen ? 0 : 46
                color: "#121b27"
                WlrLayershell.namespace: "sunshine-status"
                WlrLayershell.layer: WlrLayer.Overlay

                RowLayout {
                    anchors.fill: parent
                    anchors.leftMargin: 16
                    anchors.rightMargin: 16
                    spacing: 10
                    Rectangle {
                        implicitWidth: 7
                        implicitHeight: 7
                        radius: 4
                        color: "#71cfb1"
                    }
                    Text {
                        text: "SUNSHINE"
                        color: "#dce3ec"
                        font.pixelSize: 12
                        font.letterSpacing: 2
                        visible: top.width >= 650
                    }
                    Rectangle {
                        implicitWidth: 1
                        implicitHeight: 20
                        color: "#334150"
                    }
                    Repeater {
                        model: I3.workspaces
                        ShellButton {
                            required property var modelData
                            text: modelData.name
                            selected: I3.focusedWorkspace === modelData
                            hint: "切换工作区 " + modelData.name
                            onClicked: modelData.activate()
                        }
                    }
                    Text {
                        Layout.fillWidth: true
                        Layout.minimumWidth: 0
                        text: root.activeWindow ? root.activeWindow.title : "独立桌面"
                        textFormat: Text.PlainText
                        elide: Text.ElideRight
                        color: "#8e9fb3"
                        font.pixelSize: 13
                        verticalAlignment: Text.AlignVCenter
                    }
                    Text {
                        visible: top.width >= 1000
                        text: desktop.modelData.width + " × " + desktop.modelData.height
                        color: "#8e9fb3"
                        font.pixelSize: 12
                    }
                    ShellButton {
                        text: root.audio ? (root.audio.muted ? "静音" : "音量 " + Math.round(root.audio.volume * 100) + "%") : "音频连接中"
                        hint: "点击静音 · 滚轮调节串流音量"
                        onClicked: {
                            if (root.audio)
                                root.audio.muted = !root.audio.muted;
                        }
                        WheelHandler {
                            onWheel: event => {
                                if (root.audio)
                                    root.audio.volume = Math.max(0, Math.min(1, root.audio.volume + (event.angleDelta.y > 0 ? 0.05 : -0.05)));
                            }
                        }
                    }
                    Text {
                        text: Qt.formatDateTime(clock.date, top.width >= 700 ? "MM/dd  ddd   HH:mm" : "HH:mm")
                        color: "#e3eaf3"
                        font.pixelSize: 13
                    }
                }
                Rectangle {
                    anchors.bottom: parent.bottom
                    width: parent.width
                    height: 1
                    color: "#2b3949"
                }
            }

            // Quickshell supplies a platform-specific PanelWindow at runtime.
            // qmllint disable uncreatable-type
            PanelWindow {
                // qmllint enable uncreatable-type
                id: dock
                screen: desktop.modelData
                visible: !root.fullscreen || root.revealed
                anchors {
                    bottom: true
                }
                // Qt tooling cannot resolve this runtime PanelWindow group.
                // qmllint disable unqualified unresolved-type
                margins.bottom: 10
                // qmllint enable unqualified unresolved-type
                implicitWidth: Math.min(desktop.modelData.width - 24, Math.max(270, 160 + windows.contentWidth))
                implicitHeight: 70
                exclusiveZone: root.fullscreen ? 0 : 84
                color: "transparent"
                WlrLayershell.namespace: "sunshine-dock"
                WlrLayershell.layer: WlrLayer.Overlay

                Rectangle {
                    anchors.fill: parent
                    radius: 18
                    color: "#ed172231"
                    border.color: "#425266"
                    border.width: 1
                    RowLayout {
                        anchors.fill: parent
                        anchors.margins: 10
                        spacing: 8
                        ShellButton {
                            implicitWidth: 48
                            implicitHeight: 48
                            text: ""
                            imageSource: Qt.resolvedUrl("icons/terminal.svg")
                            hint: "打开终端"
                            onClicked: Quickshell.execDetached(["foot", "/bin/bash"])
                        }
                        ShellButton {
                            implicitWidth: 48
                            implicitHeight: 48
                            text: ""
                            imageSource: Qt.resolvedUrl("icons/folder.svg")
                            hint: "打开文件管理器"
                            onClicked: Quickshell.execDetached(["dolphin"])
                        }
                        Rectangle {
                            implicitWidth: 1
                            Layout.fillHeight: true
                            Layout.topMargin: 8
                            Layout.bottomMargin: 8
                            color: "#425266"
                        }
                        ListView {
                            id: windows
                            Layout.fillWidth: true
                            Layout.fillHeight: true
                            Layout.minimumWidth: 80
                            orientation: ListView.Horizontal
                            spacing: 6
                            clip: true
                            boundsBehavior: Flickable.StopAtBounds
                            model: ToplevelManager.toplevels
                            delegate: ShellButton {
                                id: windowButton
                                required property var modelData
                                readonly property var entry: DesktopEntries.heuristicLookup(modelData.appId)
                                width: 170
                                height: 48
                                text: modelData.title || modelData.appId || "窗口"
                                hint: text
                                selected: modelData.activated
                                imageSource: (entry && entry.icon && Quickshell.hasThemeIcon(entry.icon)) ? Quickshell.iconPath(entry.icon) : Qt.resolvedUrl("icons/window.svg")
                                onClicked: Qt.callLater(() => root.activateWindow(modelData))
                                Rectangle {
                                    anchors.bottom: parent.bottom
                                    anchors.bottomMargin: 2
                                    anchors.horizontalCenter: parent.horizontalCenter
                                    width: windowButton.selected ? 20 : 5
                                    height: 3
                                    radius: 2
                                    color: windowButton.selected ? "#79d3df" : "#64758a"
                                }
                            }
                            WheelHandler {
                                onWheel: event => {
                                    windows.contentX = Math.max(0, Math.min(Math.max(0, windows.contentWidth - windows.width), windows.contentX - event.angleDelta.y));
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}
