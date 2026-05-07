import SwiftUI

struct SpotIntakeWorkspaceView: View {
    @ObservedObject var service: SpotCoreService

    var body: some View {
        VStack(alignment: .leading, spacing: 18) {
            HStack {
                VStack(alignment: .leading, spacing: 4) {
                    Text("Intake And Run Start")
                        .font(.title2)
                        .fontWeight(.semibold)
                    Text("Accepted workbook intake and native run launch.")
                        .foregroundStyle(.secondary)
                }
                Spacer()
                Button("Intake Workbook") {
                    Task { await service.pickAndIntakeWorkbook() }
                }
                Button("Refresh Intake") {
                    Task { await service.refreshUploads() }
                }
            }

            GroupBox("Run Start") {
                Grid(alignment: .leading, horizontalSpacing: 16, verticalSpacing: 12) {
                    GridRow {
                        Text("Run ID").foregroundStyle(.secondary)
                        TextField("run-...", text: $service.newRunID)
                            .textFieldStyle(.roundedBorder)
                    }
                    GridRow {
                        Text("Language").foregroundStyle(.secondary)
                        TextField("de", text: $service.startLanguage)
                            .textFieldStyle(.roundedBorder)
                    }
                    GridRow {
                        Text("Review Mode").foregroundStyle(.secondary)
                        Picker("Review Mode", selection: $service.startReviewMode) {
                            Text("partial").tag("partial")
                            Text("full").tag("full")
                        }
                        .pickerStyle(.menu)
                    }
                    GridRow {
                        Text("Limit").foregroundStyle(.secondary)
                        TextField("optional", text: $service.startLimit)
                            .textFieldStyle(.roundedBorder)
                    }
                    GridRow {
                        Text("Selected Upload").foregroundStyle(.secondary)
                        if service.availableUploads.isEmpty {
                            Text("No intake records loaded.")
                                .foregroundStyle(.secondary)
                        } else {
                            Picker("Selected Upload", selection: $service.selectedUploadID) {
                                ForEach(service.availableUploads) { upload in
                                    Text(uploadLabel(upload)).tag(upload.uploadID)
                                }
                            }
                            .pickerStyle(.menu)
                        }
                    }
                }

                HStack {
                    Button("Start Run") {
                        Task { await service.startRunFromSelectedUpload() }
                    }
                    .disabled(service.selectedUploadID.isEmpty)
                    if !service.uploadMessage.isEmpty {
                        Text(service.uploadMessage)
                            .foregroundStyle(.secondary)
                    }
                }
                .padding(.top, 12)
            }

            GroupBox("Watch Folder Automation") {
                VStack(alignment: .leading, spacing: 12) {
                    Text("Drop `.xlsx` files into the inbox folder and {spot} will queue them automatically. Successfully queued files move to processed; failures move to failed.")
                        .foregroundStyle(.secondary)
                    Grid(alignment: .leading, horizontalSpacing: 16, verticalSpacing: 12) {
                        GridRow {
                            Text("Inbox Folder").foregroundStyle(.secondary)
                            Text(service.nativeConfig.intakeWatchDir)
                                .textSelection(.enabled)
                        }
                        GridRow {
                            Text("Processed Folder").foregroundStyle(.secondary)
                            Text(service.nativeConfig.intakeArchiveDir)
                                .textSelection(.enabled)
                        }
                        GridRow {
                            Text("Failed Folder").foregroundStyle(.secondary)
                            Text(service.nativeConfig.intakeFailedDir)
                                .textSelection(.enabled)
                        }
                    }

                    Toggle(
                        "Automatically start the next watched workbook when the runtime is free",
                        isOn: Binding(
                            get: { service.nativeConfig.autoStartWatchFolder },
                            set: { service.setAutoStartWatchFolder($0) }
                        )
                    )

                    Text(service.watchFolderStatus)
                        .foregroundStyle(.secondary)

                    HStack {
                        VStack(alignment: .leading, spacing: 10) {
                            folderSelectorRow(
                                title: "Set Inbox Folder",
                                path: service.nativeConfig.intakeWatchDir,
                                chooseAction: service.chooseWatchFolder
                            )
                            folderSelectorRow(
                                title: "Set Processed Folder",
                                path: service.nativeConfig.intakeArchiveDir,
                                chooseAction: service.chooseProcessedFolder
                            )
                            folderSelectorRow(
                                title: "Set Failed Folder",
                                path: service.nativeConfig.intakeFailedDir,
                                chooseAction: service.chooseFailedFolder
                            )
                        }
                    }

                    HStack {
                        Button("Open Inbox Folder") {
                            service.openWatchFolder()
                        }
                        Button("Open Processed Folder") {
                            service.openProcessedIntakeFolder()
                        }
                        Button("Open Failed Folder") {
                            service.openFailedIntakeFolder()
                        }
                        Button("Scan Now") {
                            Task { await service.triggerWatchedFolderScan() }
                        }
                    }
                }
            }

            GroupBox("Intake Queue") {
                if service.availableUploads.isEmpty {
                    ContentUnavailableView(
                        "No intake records",
                        systemImage: "tray",
                        description: Text("Intake a workbook to create an accepted upload record that can be started as a native run.")
                    )
                } else {
                    List(service.availableUploads, selection: $service.selectedUploadID) { upload in
                        VStack(alignment: .leading, spacing: 6) {
                            HStack {
                                Text(upload.filename ?? upload.uploadID)
                                    .font(.headline)
                                Spacer()
                                Text(upload.status ?? "unknown")
                                    .foregroundStyle(.secondary)
                            }
                            Text(upload.uploadID)
                                .font(.caption)
                                .foregroundStyle(.secondary)
                            if let message = upload.message, !message.isEmpty {
                                Text(message)
                                    .font(.caption)
                                    .foregroundStyle(.secondary)
                                    .lineLimit(2)
                            }
                        }
                        .padding(.vertical, 4)
                        .tag(upload.uploadID)
                    }
                    .listStyle(.inset)
                }
            }

            Spacer()
        }
        .padding(24)
        .frame(minWidth: 980, minHeight: 720)
    }

    private func uploadLabel(_ upload: SpotUploadRecord) -> String {
        "\(upload.filename ?? upload.uploadID) · \(upload.status ?? "unknown")"
    }

    @ViewBuilder
    private func folderSelectorRow(title: String, path: String, chooseAction: @escaping () -> Void) -> some View {
        HStack(alignment: .firstTextBaseline, spacing: 12) {
            Button(title, action: chooseAction)
            Button(path) {
                service.openFolder(at: path)
            }
            .buttonStyle(.link)
            .lineLimit(1)
            .help(path)
        }
    }
}
