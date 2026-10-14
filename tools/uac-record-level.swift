// macOS diagnostic: record the default input for N seconds and report the
// level and dominant frequency, to verify audio sent through the board's USB
// microphone (UAC2) gadget. Requires microphone permission for the terminal.
// swiftc tools/uac-record-level.swift -o /tmp/uac-record-level && /tmp/uac-record-level 3
// Optional second argument selects a device name/manufacturer without changing
// the system default input (UAC2 may advertise its interface as Capture Inactive).
import AVFoundation
import CoreAudio
import AudioToolbox

func defaultInputName() -> String {
    var id = AudioDeviceID(0)
    var size = UInt32(MemoryLayout<AudioDeviceID>.size)
    var address = AudioObjectPropertyAddress(mSelector: kAudioHardwarePropertyDefaultInputDevice,
                                             mScope: kAudioObjectPropertyScopeGlobal, mElement: kAudioObjectPropertyElementMain)
    AudioObjectGetPropertyData(AudioObjectID(kAudioObjectSystemObject), &address, 0, nil, &size, &id)
    var name: CFString = "" as CFString
    size = UInt32(MemoryLayout<CFString>.size)
    address.mSelector = kAudioObjectPropertyName
    AudioObjectGetPropertyData(id, &address, 0, nil, &size, &name)
    return name as String
}

let seconds = Double(CommandLine.arguments.dropFirst().first ?? "3") ?? 3
guard AVCaptureDevice.authorizationStatus(for: .audio) == .authorized else {
    FileHandle.standardError.write(Data("macOS microphone permission is required for the recording terminal\n".utf8))
    exit(1)
}
let engine = AVAudioEngine()
let input = engine.inputNode
var selectedName = defaultInputName()
var selectedManufacturer = ""
if CommandLine.arguments.count > 2 {
    let requested = CommandLine.arguments[2]
    var address = AudioObjectPropertyAddress(mSelector: kAudioHardwarePropertyDevices,
        mScope: kAudioObjectPropertyScopeGlobal, mElement: kAudioObjectPropertyElementMain)
    var size: UInt32 = 0
    AudioObjectGetPropertyDataSize(AudioObjectID(kAudioObjectSystemObject), &address, 0, nil, &size)
    var devices = [AudioDeviceID](repeating: 0, count: Int(size) / MemoryLayout<AudioDeviceID>.size)
    AudioObjectGetPropertyData(AudioObjectID(kAudioObjectSystemObject), &address, 0, nil, &size, &devices)
    var selected: AudioDeviceID = 0
    for device in devices {
        var name: CFString = "" as CFString
        var bytes = UInt32(MemoryLayout<CFString>.size)
        var property = AudioObjectPropertyAddress(mSelector: kAudioObjectPropertyName,
            mScope: kAudioObjectPropertyScopeGlobal, mElement: kAudioObjectPropertyElementMain)
        AudioObjectGetPropertyData(device, &property, 0, nil, &bytes, &name)
        var manufacturer: CFString = "" as CFString
        property.mSelector = kAudioObjectPropertyManufacturer
        bytes = UInt32(MemoryLayout<CFString>.size)
        AudioObjectGetPropertyData(device, &property, 0, nil, &bytes, &manufacturer)
        if (name as String).contains(requested) || (manufacturer as String).contains(requested) {
            selected = device; selectedName = name as String; selectedManufacturer = manufacturer as String; break
        }
    }
    guard selected != 0, let unit = input.audioUnit else { fatalError("Requested USB input is unavailable") }
    let status = AudioUnitSetProperty(unit, kAudioOutputUnitProperty_CurrentDevice,
        kAudioUnitScope_Global, 0, &selected, UInt32(MemoryLayout<AudioDeviceID>.size))
    guard status == noErr else { fatalError("Cannot select USB input: \(status)") }
}
let format = input.inputFormat(forBus: 0)
var samples: [Float] = []
input.installTap(onBus: 0, bufferSize: 4096, format: format) { buffer, _ in
    guard let data = buffer.floatChannelData else { return }
    samples.append(contentsOf: UnsafeBufferPointer(start: data[0], count: Int(buffer.frameLength)))
}
try engine.start()
Thread.sleep(forTimeInterval: seconds)
engine.stop()

let rms = sqrt(samples.reduce(0) { $0 + $1 * $1 } / Float(max(samples.count, 1)))
// Zero crossings per second approximate the frequency of a pure tone.
var crossings = 0
for i in 1..<max(samples.count, 1) where (samples[i - 1] < 0) != (samples[i] < 0) { crossings += 1 }
let first = samples.firstIndex(where: { abs($0) > 0.001 }) ?? 0
let last = samples.lastIndex(where: { abs($0) > 0.001 }) ?? first
let frequency = Double(crossings) / 2 / (Double(max(last - first + 1, 1)) / format.sampleRate)
let result: [String: Any] = ["device": selectedName, "manufacturer": selectedManufacturer,
    "rate": format.sampleRate, "samples": samples.count, "rms": rms, "frequency": frequency]
print(String(data: try JSONSerialization.data(withJSONObject: result, options: .sortedKeys), encoding: .utf8)!)
