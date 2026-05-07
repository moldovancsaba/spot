import SwiftUI

struct SpotArtifactWorkspaceView: View {
    @ObservedObject var service: SpotCoreService

    var body: some View {
        VStack(alignment: .leading, spacing: 18) {
            HStack {
                VStack(alignment: .leading, spacing: 4) {
                    Text("Run Operations And Artifacts")
                        .font(.title2)
                        .fontWeight(.semibold)
                    Text(service.selectedRunID.isEmpty ? "No run selected" : "Managing \(service.selectedRunID)")
                        .foregroundStyle(.secondary)
                }
                Spacer()
                Button("Refresh Run") {
                    Task { await service.refreshRuntimeSnapshot() }
                }
                Button("Refresh Artifacts") {
                    Task { await service.loadArtifactsForSelectedRun() }
                }
                .disabled(service.selectedRunID.isEmpty)
            }

            GroupBox("Lifecycle Controls") {
                HStack {
                    Button("Pause") { Task { await service.performRunOperation("pause") } }
                    Button("Resume") { Task { await service.performRunOperation("resume") } }
                    Button("Cancel") { Task { await service.performRunOperation("cancel") } }
                    Button("Retry") { Task { await service.performRunOperation("retry") } }
                    Button("Recover") { Task { await service.performRunOperation("recover") } }
                }
                .disabled(service.selectedRunID.isEmpty)
            }

            GroupBox("Sign-off") {
                VStack(alignment: .leading, spacing: 12) {
                    Picker("Decision", selection: $service.signoffDecision) {
                        Text("accepted").tag("accepted")
                        Text("accepted_with_conditions").tag("accepted_with_conditions")
                        Text("not_accepted").tag("not_accepted")
                    }
                    .pickerStyle(.menu)

                    Text("Note")
                        .font(.headline)
                    TextEditor(text: $service.signoffNote)
                        .frame(minHeight: 100)

                    HStack {
                        Button("Submit Sign-off") {
                            Task { await service.submitSignoff() }
                        }
                        .disabled(service.selectedRunID.isEmpty)
                        if !service.artifactMessage.isEmpty {
                            Text(service.artifactMessage)
                                .foregroundStyle(.secondary)
                        }
                    }
                }
            }

            GroupBox("Artifacts") {
                if service.activeArtifacts.isEmpty {
                    ContentUnavailableView(
                        "No artifacts loaded",
                        systemImage: "folder",
                        description: Text("Select a run and refresh artifacts to inspect native outputs and audit files.")
                    )
                } else {
                    List(service.activeArtifacts) { artifact in
                        HStack {
                            VStack(alignment: .leading, spacing: 4) {
                                Text(artifact.name)
                                    .font(.headline)
                                Text(artifact.purpose ?? "Run artifact")
                                    .font(.caption)
                                    .foregroundStyle(.secondary)
                                Text(artifact.path)
                                    .font(.caption2)
                                    .foregroundStyle(.secondary)
                                    .lineLimit(1)
                            }
                            Spacer()
                            Text(ByteCountFormatter.string(fromByteCount: Int64(artifact.bytes), countStyle: .file))
                                .foregroundStyle(.secondary)
                            Button("Open") {
                                service.openArtifact(artifact)
                            }
                        }
                        .padding(.vertical, 4)
                    }
                    .listStyle(.inset)
                }
            }

            Spacer()
        }
        .padding(24)
        .frame(minWidth: 980, minHeight: 720)
    }
}
