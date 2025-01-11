import sounddevice as sd
import matplotlib.pyplot as plt
import numpy as np
import tkinter as tk
from tkinter import ttk
from datetime import datetime, timedelta
import multiprocessing as mp
import queue as threading_queue
import wave


# Function to list all available input devices
# Ignoring devices with "Background Music" in their name
def list_audio_devices():
    devices = sd.query_devices()
    input_devices = [
        d
        for d in devices
        if d["max_input_channels"] > 0 and "Background Music" not in d["name"]
    ]
    for i, device in enumerate(input_devices):
        device["index"] = devices.index(device)
    return input_devices


# Function to display a single dialog to select device, sample rate, block size, and file name
def get_audio_settings(devices):
    def on_submit():
        selected_device.set(device_menu.get())
        selected_sample_rate.set(sample_rate_entry.get())
        selected_block_size.set(block_size_entry.get())
        selected_file_name.set(file_name_entry.get())
        root.destroy()

    root = tk.Tk()
    root.title("Audio Settings")

    # Dropdown for audio device selection
    tk.Label(root, text="Select Audio Device:").grid(row=0, column=0)
    device_names = [f"{d['index']}: {d['name']}" for d in devices]
    selected_device = tk.StringVar(value=device_names[0])
    device_menu = ttk.Combobox(root, textvariable=selected_device, values=device_names)
    device_menu.grid(row=0, column=1)

    # Entry for sample rate
    tk.Label(root, text="Sample Rate:").grid(row=1, column=0)
    selected_sample_rate = tk.StringVar(value="48000")
    sample_rate_entry = tk.Entry(root, textvariable=selected_sample_rate)
    sample_rate_entry.grid(row=1, column=1)

    # Entry for block size
    tk.Label(root, text="Block Size:").grid(row=2, column=0)
    selected_block_size = tk.StringVar(value="1200")
    block_size_entry = tk.Entry(root, textvariable=selected_block_size)
    block_size_entry.grid(row=2, column=1)

    # Entry for file name
    tk.Label(root, text="File Name:").grid(row=3, column=0)
    selected_file_name = tk.StringVar(value="output.wav")
    file_name_entry = tk.Entry(root, textvariable=selected_file_name)
    file_name_entry.grid(row=3, column=1)

    # Submit button
    submit_button = tk.Button(root, text="Submit", command=on_submit)
    submit_button.grid(row=4, columnspan=2)

    root.mainloop()

    return (
        int(selected_device.get().split(":")[0]),
        int(selected_sample_rate.get()),
        int(selected_block_size.get()),
        selected_file_name.get(),
    )


# Function to capture audio in a separate process and save to a .wav file
def audio_capture_process(out_queue, device_id, sample_rate, blocksize, file_name):
    print(
        f"Device ID: {device_id}, Sample Rate: {sample_rate}, Block Size: {blocksize}"
    )
    internal_queue = threading_queue.Queue()
    adc_time_offset = None

    wav_file = wave.open(file_name, "wb")
    wav_file.setnchannels(1)
    wav_file.setsampwidth(2)  # Assuming 16-bit audio
    wav_file.setframerate(sample_rate)

    def audio_callback(indata, frames, time, status):
        current_time = datetime.now().timestamp()
        nonlocal adc_time_offset
        if status:
            print(status)

        adc_time = time.inputBufferAdcTime
        if adc_time_offset is None:
            adc_time_offset = current_time - adc_time

        adjusted_adc_time = adc_time + adc_time_offset
        print(
            f"ADC Time: {adjusted_adc_time}, "
            f"Current Time: {current_time}, "
            f"Offset: {adc_time_offset}, "
            f"Input Buffer Time: {time.inputBufferAdcTime}, "
            f"Current Time: {time.currentTime}"
        )
        internal_queue.put((indata.copy(), adjusted_adc_time))
        wav_file.writeframes(indata.tobytes())

    def send_data():
        while True:
            try:
                data, adjusted_time = internal_queue.get()
                out_queue.put((data, adjusted_time))
            except Exception as e:
                print(f"Error in sending data: {e}")
                break

    with sd.InputStream(
        device=device_id,
        channels=1,
        samplerate=sample_rate,
        blocksize=blocksize,
        callback=audio_callback,
    ):
        send_data()

    wav_file.close()


# Function to start the live spectrogram
def start_spectrogram(queue, sample_rate, block_size):
    plt.ion()
    fig, ax = plt.subplots()
    time_window = 10  # Display the last 10 seconds
    Z = np.zeros((block_size // 2 + 1, time_window * sample_rate // block_size))

    img = ax.imshow(
        Z,
        aspect="auto",
        origin="lower",
        extent=[0, time_window, 0, sample_rate // 2],
        cmap="magma",
    )
    plt.colorbar(img)
    ax.set_xlabel("Time")
    ax.set_ylabel("Frequency (Hz)")

    try:
        first_time = None
        cumulative_time = 0
        while plt.fignum_exists(fig.number):
            while not queue.empty():
                data, adjusted_time = queue.get()
                spectrum = np.abs(np.fft.rfft(data[:, 0]))
                print(
                    f"max data {np.max(data)} "
                    f"min data {np.min(data)} "
                    f"max spectrum {np.max(spectrum)} "
                    f"min spectrum {np.min(spectrum)}"
                )
                Z[:, :-1] = Z[:, 1:]
                Z[:, -1] = spectrum

                # Update the x-axis to show real local time
                current_time = datetime.fromtimestamp(adjusted_time)
                time_labels = [
                    (current_time - timedelta(seconds=time_window - i)).strftime(
                        "%H:%M:%S"
                    )
                    for i in range(time_window)
                ]
                ax.set_xticks(np.linspace(0, time_window, len(time_labels)))
                ax.set_xticklabels(time_labels, rotation=45)

                img.set_data(Z)
            plt.pause(0.01)
    except KeyboardInterrupt:
        pass
    except Exception as e:
        print(f"Error: {e}")
    finally:
        plt.close()


if __name__ == "__main__":
    devices = list_audio_devices()
    if not devices:
        print("No input devices found.")
        exit(1)

    selected_device_id, selected_sample_rate, blocksize, file_name = get_audio_settings(
        devices
    )

    selected_device = devices[
        [i for i in range(len(devices)) if devices[i]["index"] == selected_device_id][0]
    ]

    print(f"Selected Device: {selected_device['name']} at index {selected_device_id}")
    print(f"Selected Sample Rate: {selected_sample_rate}")
    print(f"Selected Block Size: {blocksize}")
    print(f"Saving to file: {file_name}")

    audio_queue = mp.Queue()
    audio_process = mp.Process(
        target=audio_capture_process,
        args=(
            audio_queue,
            selected_device_id,
            selected_sample_rate,
            blocksize,
            file_name,
        ),
    )
    audio_process.daemon = True
    audio_process.start()

    start_spectrogram(audio_queue, selected_sample_rate, blocksize)
