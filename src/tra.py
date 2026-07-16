import asyncio


async def fetch_data(task_id, delay):
    print(f"Task {task_id}: Starting...")
    await asyncio.sleep(delay)
    print(f"Task {task_id}: Done!")
    return f"Result {task_id}"


async def main():
    # 1. Open the task group
    async with asyncio.TaskGroup() as tg:
        # 2. Spawn tasks into the group
        task1 = tg.create_task(fetch_data("A", 2))
        task2 = tg.create_task(fetch_data("B", 1))
        task3 = tg.create_task(fetch_data("C", 1.5))

    # 3. Once the 'async with' block exits, ALL tasks are guaranteed to be finished!
    # Retrieve the results using .result()
    results = [task1.result(), task2.result(), task3.result()]
    print(f"All tasks complete. Results: {results}")


# Run the async event loop
asyncio.run(main())


# def run_writer(server, port, username):
#     """Read lines from the user and send each to the server."""
#     sock = connect(server, port, common.make_hello(MODE_WRITER, username))
#     logger.info("Connected as {} (writer). Type messages or '/image <path>'; Ctrl-C to quit.".format(username))
#     try:
#         while True:
#             sending_mode = input(SEND_MENU)
#
#             text = input(MESSAGE_PROMPT)
#             if text == EMPTY_STRING:
#                 continue
#             start_deliver_time = dt.now()
#             if sending_mode == SEND_FILE:
#                 # 1. First, open the file in 'w' mode to write the incoming text
#                 with open(LETTER_FILE_PATH, WRITE_MODE) as f:
#                     f.write(text)
#
#                 # 2. Open the file in 'r' (read) mode to read the lines out safely
#                 with open(LETTER_FILE_PATH, READ_MODE) as f:
#                     for line in f:
#                         clean_line = line.strip()
#                         encoded_frame = common.encode(common.make_msg(clean_line)) + NEWLINE_BYTES
#                         sock.sendall(encoded_frame)
#                         if clean_line == EMPTY_STRING:
#                             continue
#                 logger.info("File written and contents completely sent")
#             if sending_mode == SEND_IMAGE:
#                 # Create a custom JSON structure for the image
#                 # Ensure common.make_msg can accept custom fields, or construct it directly:
#                 image_payload = common.make_image(text, username)
#
#                 # Encode and append a newline character so common.LineBuffer knows where it ends
#                 encoded_frame = common.encode(image_payload) + NEWLINE_BYTES
#                 sock.sendall(encoded_frame)
#                 logger.info("Sent image: {} ".format(text))
#             if sending_mode == SEND_CHAT:
#                 # Regular text chat flow
#                 # Adding standard newline byte if common.encode does not handle it automatically
#                 encoded_frame = common.encode(common.make_msg(text)) + NEWLINE_BYTES
#                 sock.sendall(encoded_frame)
#                 logger.info(f"Sent message")
#             if sending_mode == SEND_MATRIX:
#                 encoded_frame = common.encode(common.make_matrix(text, username)) + NEWLINE_BYTES
#                 sock.sendall(encoded_frame)
#                 logger.info(f"Sent Matrix")
#             if sending_mode == SEND_PREMONITIONS:
#                 encoded_frame = common.encode(common.make_premonitions(text, username)) + NEWLINE_BYTES
#                 sock.sendall(encoded_frame)
#                 logger.info(f"Sent premonitions")
#
#             end_deliver_time = dt.now()
#             deliver_timer(start_deliver_time, end_deliver_time)
#     except (EOFError, KeyboardInterrupt):
#         logger.info("\nDisconnecting...")
#     except (socket.error, OSError) as exc:
#         logger.info("\nConnection lost: {} ".format(exc))
#     finally:
#         sock.close()
