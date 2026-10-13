// macOS diagnostic: record the default input for N seconds and report the
// level and dominant frequency, to verify audio sent through the board's USB
// microphone (UAC2) gadget. Requires microphone permission for the terminal.
// swiftc tools/uac-record-level.swift -o /tmp/uac-record-level && /tmp/uac-record-level 3
import AVFoundation
import CoreAudio

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
let engine = AVAudioEngine()
let input = engine.inputNode
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
let frequency = Double(crossings) / 2 / (Double(samples.count) / format.sampleRate)
print(String(format: "{\"device\":\"%@\",\"rate\":%.0f,\"samples\":%d,\"rms\":%.4f,\"frequency\":%.1f}",
             defaultInputName(), format.sampleRate, samples.count, rms, frequency))
