import SwiftUI

struct SpotSettingsView: View {
    @AppStorage("spotAppearanceMode") private var appearanceMode = SpotAppearanceMode.system.rawValue
    @ObservedObject var service: SpotCoreService

    var body: some View {
        Form {
            Picker("Appearance", selection: $appearanceMode) {
                ForEach(SpotAppearanceMode.allCases) { mode in
                    Text(mode.label).tag(mode.rawValue)
                }
            }
            LabeledContent("Python Binary", value: service.nativeConfig.pythonBin.isEmpty ? "Not configured" : service.nativeConfig.pythonBin)
            LabeledContent("Runs Directory", value: service.nativeConfig.runsDir)
            LabeledContent("Logs Directory", value: service.nativeConfig.logsDir)
            LabeledContent("Locked SSOT Path", value: service.nativeConfig.lockedSSOTPath)
            LabeledContent("Port", value: "\(service.nativeConfig.port)")
            LabeledContent("Watch Folder", value: service.nativeConfig.intakeWatchDir)
            LabeledContent("Processed Folder", value: service.nativeConfig.intakeArchiveDir)
            LabeledContent("Failed Folder", value: service.nativeConfig.intakeFailedDir)
            LabeledContent("Watch Auto-Start", value: service.nativeConfig.autoStartWatchFolder ? "Enabled" : "Disabled")
            LabeledContent("Mode", value: "Native local")
            LabeledContent("Native Config", value: "\(NSHomeDirectory())/Library/Application Support/spot/native-runtime.env")
            Text("Configure native runtime values in ~/Library/Application Support/spot/native-runtime.env before launching the bundled runtime. The watch folder can also be changed from Intake Workspace.")
                .font(.caption)
                .foregroundStyle(.secondary)
            HStack {
                Button("Open Native Config") { service.openNativeConfig() }
                Button("Rewrite Config Template") { service.rewriteNativeConfigTemplate() }
                Button("Reload Config") { service.reloadNativeConfig() }
            }
        }
        .formStyle(.grouped)
        .padding(20)
        .frame(minWidth: 760, minHeight: 480)
    }
}
