import QtQuick
import Quickshell
import Quickshell.Wayland

ShellRoot {
    Variants {
        model: Quickshell.screens
        PanelWindow {
            id: desktopWindow
            property var modelData
            screen: modelData

            WlrLayershell.layer: WlrLayer.Bottom
            WlrLayershell.namespace: "quickshell:agility-desktop-widgets"
            WlrLayershell.keyboardFocus: WlrKeyboardFocus.None

            anchors {
                top: true
                bottom: true
                left: true
                right: true
            }
            color: "transparent"

            mask: Region {
                Region { item: clockWidget }
                Region { item: sysinfoWidget }
                Region { item: calendarWidget }
                Region { item: mediaWidget }
                Region { item: weatherWidget }
                Region { item: posterWidget }
                Region { item: batteryWidget }
                Region { item: volumeWidget }
                Region { item: networkWidget }
                Region { item: notesWidget }
                Region { item: todoWidget }
                Region { item: timerWidget }
                Region { item: thermalWidget }
                Region { item: quoteWidget }
                Region { item: clipboardWidget }
                Region { item: cryptoWidget }
                Region { item: worldclockWidget }
                Region { item: gitWidget }
                Region { item: resourcewheelWidget }
                Region { item: visualizerWidget }
                Region { item: habitsWidget }
                Region { item: pingWidget }
                Region { item: storagemapWidget }
                Region { item: calcWidget }
            }

            Item {
                id: widgetsLayer
                anchors.fill: parent

                Clock {
                    id: clockWidget
                    visible: Theme.widgetVisibility["clock"] !== false
                    screenWidth: desktopWindow.width
                    screenHeight: desktopWindow.height
                }

                SystemInfo {
                    id: sysinfoWidget
                    visible: Theme.widgetVisibility["sysinfo"] !== false
                    screenWidth: desktopWindow.width
                    screenHeight: desktopWindow.height
                }

                CalendarWidget {
                    id: calendarWidget
                    visible: Theme.widgetVisibility["calendar"] !== false
                    screenWidth: desktopWindow.width
                    screenHeight: desktopWindow.height
                }

                MediaWidget {
                    id: mediaWidget
                    visible: Theme.widgetVisibility["media"] !== false
                    screenWidth: desktopWindow.width
                    screenHeight: desktopWindow.height
                }

                WeatherWidget {
                    id: weatherWidget
                    visible: Theme.widgetVisibility["weather"] !== false
                    screenWidth: desktopWindow.width
                    screenHeight: desktopWindow.height
                }

                PosterWidget {
                    id: posterWidget
                    visible: Theme.widgetVisibility["poster"] !== false
                    screenWidth: desktopWindow.width
                    screenHeight: desktopWindow.height
                }

                BatteryWidget {
                    id: batteryWidget
                    visible: Theme.widgetVisibility["battery"] !== false
                    screenWidth: desktopWindow.width
                    screenHeight: desktopWindow.height
                }

                VolumeBrightnessWidget {
                    id: volumeWidget
                    visible: Theme.widgetVisibility["quickcontrols"] !== false
                    screenWidth: desktopWindow.width
                    screenHeight: desktopWindow.height
                }

                NetworkWidget {
                    id: networkWidget
                    visible: Theme.widgetVisibility["network"] !== false
                    screenWidth: desktopWindow.width
                    screenHeight: desktopWindow.height
                }

                NotesWidget {
                    id: notesWidget
                    visible: Theme.widgetVisibility["notes"] !== false
                    screenWidth: desktopWindow.width
                    screenHeight: desktopWindow.height
                }

                TodoWidget {
                    id: todoWidget
                    visible: Theme.widgetVisibility["todo"] !== false
                    screenWidth: desktopWindow.width
                    screenHeight: desktopWindow.height
                }

                TimerWidget {
                    id: timerWidget
                    visible: Theme.widgetVisibility["timer"] !== false
                    screenWidth: desktopWindow.width
                    screenHeight: desktopWindow.height
                }

                ThermalWidget {
                    id: thermalWidget
                    visible: Theme.widgetVisibility["thermal"] !== false
                    screenWidth: desktopWindow.width
                    screenHeight: desktopWindow.height
                }

                QuoteWidget {
                    id: quoteWidget
                    visible: Theme.widgetVisibility["quote"] !== false
                    screenWidth: desktopWindow.width
                    screenHeight: desktopWindow.height
                }

                ClipboardWidget {
                    id: clipboardWidget
                    visible: Theme.widgetVisibility["clipboard"] !== false
                    screenWidth: desktopWindow.width
                    screenHeight: desktopWindow.height
                }

                CryptoWidget {
                    id: cryptoWidget
                    visible: Theme.widgetVisibility["crypto"] !== false
                    screenWidth: desktopWindow.width
                    screenHeight: desktopWindow.height
                }

                WorldClockWidget {
                    id: worldclockWidget
                    visible: Theme.widgetVisibility["worldclock"] !== false
                    screenWidth: desktopWindow.width
                    screenHeight: desktopWindow.height
                }

                GitDashboardWidget {
                    id: gitWidget
                    visible: Theme.widgetVisibility["git"] !== false
                    screenWidth: desktopWindow.width
                    screenHeight: desktopWindow.height
                }

                ResourceWheelWidget {
                    id: resourcewheelWidget
                    visible: Theme.widgetVisibility["resourcewheel"] !== false
                    screenWidth: desktopWindow.width
                    screenHeight: desktopWindow.height
                }

                VisualizerWidget {
                    id: visualizerWidget
                    visible: Theme.widgetVisibility["visualizer"] !== false
                    screenWidth: desktopWindow.width
                    screenHeight: desktopWindow.height
                }

                HabitsWidget {
                    id: habitsWidget
                    visible: Theme.widgetVisibility["habits"] !== false
                    screenWidth: desktopWindow.width
                    screenHeight: desktopWindow.height
                }

                PingWidget {
                    id: pingWidget
                    visible: Theme.widgetVisibility["ping"] !== false
                    screenWidth: desktopWindow.width
                    screenHeight: desktopWindow.height
                }

                StorageMapWidget {
                    id: storagemapWidget
                    visible: Theme.widgetVisibility["storagemap"] !== false
                    screenWidth: desktopWindow.width
                    screenHeight: desktopWindow.height
                }

                CalcWidget {
                    id: calcWidget
                    visible: Theme.widgetVisibility["calc"] !== false
                    screenWidth: desktopWindow.width
                    screenHeight: desktopWindow.height
                }
            }
        }
    }
}
