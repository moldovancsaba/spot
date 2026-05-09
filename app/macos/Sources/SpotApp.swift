import SwiftUI

final class SpotAppLifecycleDelegate: NSObject, NSApplicationDelegate {
    var onDidFinishLaunching: (() -> Void)?
    var onWillTerminate: (() -> Void)?

    func applicationDidFinishLaunching(_ notification: Notification) {
        onDidFinishLaunching?()
    }

    func applicationShouldTerminateAfterLastWindowClosed(_ sender: NSApplication) -> Bool {
        true
    }

    func applicationWillTerminate(_ notification: Notification) {
        onWillTerminate?()
    }
}

enum SpotAppearanceMode: String, CaseIterable, Identifiable {
    case system
    case light
    case dark

    var id: String { rawValue }

    var label: String {
        switch self {
        case .system: "System"
        case .light: "Light"
        case .dark: "Dark"
        }
    }

    var colorScheme: ColorScheme? {
        switch self {
        case .system: nil
        case .light: .light
        case .dark: .dark
        }
    }
}

@main
struct SpotDesktopApp: App {
    @NSApplicationDelegateAdaptor(SpotAppLifecycleDelegate.self) private var lifecycleDelegate
    @StateObject private var service = SpotCoreService()
    @AppStorage("spotAppearanceMode") private var appearanceMode = SpotAppearanceMode.system.rawValue

    init() {
        let runtimeService = SpotCoreService()
        _service = StateObject(wrappedValue: runtimeService)
        lifecycleDelegate.onDidFinishLaunching = {
            Task {
                await runtimeService.bootstrapNativeRuntimeIfNeeded()
            }
        }
        lifecycleDelegate.onWillTerminate = {
            runtimeService.prepareForApplicationTermination()
        }
        runtimeService.startMonitoring()
    }

    var body: some Scene {
        Window("{spot}", id: "workspace") {
            SpotWorkspaceView(service: service)
                .preferredColorScheme(currentAppearance.colorScheme)
        }
        .defaultSize(width: 1220, height: 860)

        Settings {
            SpotSettingsView(service: service)
                .preferredColorScheme(currentAppearance.colorScheme)
        }
        .commands {
            CommandGroup(replacing: .appInfo) {
                Button("About {spot}") {
                    NSApp.orderFrontStandardAboutPanel(nil)
                }
            }
            CommandGroup(after: .appInfo) {
                Button("Show Workspace") {
                    service.navigate(to: .dashboard)
                    NSApp.activate(ignoringOtherApps: true)
                }
                .keyboardShortcut("1", modifiers: [.command, .shift])

                Button("Show Control Center") {
                    service.navigate(to: .control)
                    NSApp.activate(ignoringOtherApps: true)
                }
                .keyboardShortcut("2", modifiers: [.command, .shift])

                Button("Show Review Workspace") {
                    service.navigate(to: .review)
                    NSApp.activate(ignoringOtherApps: true)
                }
                .keyboardShortcut("3", modifiers: [.command, .shift])

                Button("Show Intake Workspace") {
                    service.navigate(to: .intake)
                    NSApp.activate(ignoringOtherApps: true)
                }
                .keyboardShortcut("4", modifiers: [.command, .shift])

                Button("Show Operations Workspace") {
                    service.navigate(to: .operations)
                    NSApp.activate(ignoringOtherApps: true)
                }
                .keyboardShortcut("5", modifiers: [.command, .shift])

                Divider()

                Button("Refresh Status") {
                    Task { await service.refreshRuntimeSnapshot() }
                }
                .keyboardShortcut("r", modifiers: [.command, .shift])

                Button("Launch {spot} runtime") {
                    service.launchSpot()
                }

                Button("Restart {spot} runtime") {
                    service.restartSpot()
                }

                Button("Stop {spot} runtime") {
                    service.stopSpot()
                }

                Divider()

                Button("Open Review Workspace") {
                    service.navigate(to: .review)
                    NSApp.activate(ignoringOtherApps: true)
                }

                Button("Open Intake Workspace") {
                    service.navigate(to: .intake)
                    NSApp.activate(ignoringOtherApps: true)
                }

                Button("Open Operations Workspace") {
                    service.navigate(to: .operations)
                    NSApp.activate(ignoringOtherApps: true)
                }

                Button("Open Logs") {
                    service.openLogs()
                }

                Button("Open Runs Directory") {
                    service.openRunsDirectory()
                }
            }
        }
    }

    private var currentAppearance: SpotAppearanceMode {
        SpotAppearanceMode(rawValue: appearanceMode) ?? .system
    }
}
