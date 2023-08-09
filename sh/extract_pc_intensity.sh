export https_proxy=192.168.16.5:3128
cp .sh/sharded.py /usr/local/lib/python3.8/dist-packages/cloudvolume/datasource/precomputed/skeleton/sharded.py
pip install -U pip
apt-get install tmux
pip install connected-components-3d
pip install plyfile
python main.py --config-base configs/Image-Base.yaml --config-file configs/imageEmbedding/Image-Unet-connector-extract_pc.yaml --inference MODEL.OUT_PLANES 1 SYSTEM.NUM_CPUS 0 MODEL.IMAGE_MODEL_CKPT /braindat/lab/liusl/flywire/experiment/ckpts/embeddings/checkpoint_best_Unet2.pth INFERENCE.OUTPUT_PATH /braindat/lab/liusl/flywire/experiment/extract_pc_Intensity DATASET.INPUT_PATH /braindat/lab/liusl/flywire/block_data/v2/30_percent_test_3000 MODEL.IN_PLANES 4 &
sleep 60s
python main.py --config-base configs/Image-Base.yaml --config-file configs/imageEmbedding/Image-Unet-connector-extract_pc.yaml --inference MODEL.OUT_PLANES 1 SYSTEM.NUM_CPUS 0 MODEL.IMAGE_MODEL_CKPT /braindat/lab/liusl/flywire/experiment/ckpts/embeddings/checkpoint_best_Unet2.pth INFERENCE.OUTPUT_PATH /braindat/lab/liusl/flywire/experiment/extract_pc_Intensity DATASET.INPUT_PATH /braindat/lab/liusl/flywire/block_data/v2/30_percent_test_3000 MODEL.IN_PLANES 4 &
sleep 60s
python main.py --config-base configs/Image-Base.yaml --config-file configs/imageEmbedding/Image-Unet-connector-extract_pc.yaml --inference MODEL.OUT_PLANES 1 SYSTEM.NUM_CPUS 0 MODEL.IMAGE_MODEL_CKPT /braindat/lab/liusl/flywire/experiment/ckpts/embeddings/checkpoint_best_Unet2.pth INFERENCE.OUTPUT_PATH /braindat/lab/liusl/flywire/experiment/extract_pc_Intensity DATASET.INPUT_PATH /braindat/lab/liusl/flywire/block_data/v2/30_percent_test_3000 MODEL.IN_PLANES 4 &
sleep 60s
python main.py --config-base configs/Image-Base.yaml --config-file configs/imageEmbedding/Image-Unet-connector-extract_pc.yaml --inference MODEL.OUT_PLANES 1 SYSTEM.NUM_CPUS 0 MODEL.IMAGE_MODEL_CKPT /braindat/lab/liusl/flywire/experiment/ckpts/embeddings/checkpoint_best_Unet2.pth INFERENCE.OUTPUT_PATH /braindat/lab/liusl/flywire/experiment/extract_pc_Intensity DATASET.INPUT_PATH /braindat/lab/liusl/flywire/block_data/v2/30_percent_test_3000 MODEL.IN_PLANES 4 &
sleep 60s
python main.py --config-base configs/Image-Base.yaml --config-file configs/imageEmbedding/Image-Unet-connector-extract_pc.yaml --inference MODEL.OUT_PLANES 1 SYSTEM.NUM_CPUS 0 MODEL.IMAGE_MODEL_CKPT /braindat/lab/liusl/flywire/experiment/ckpts/embeddings/checkpoint_best_Unet2.pth INFERENCE.OUTPUT_PATH /braindat/lab/liusl/flywire/experiment/extract_pc_Intensity DATASET.INPUT_PATH /braindat/lab/liusl/flywire/block_data/v2/30_percent_test_3000 MODEL.IN_PLANES 4 &
sleep 600s
python main.py --config-base configs/Image-Base.yaml --config-file configs/imageEmbedding/Image-Unet-connector-extract_pc.yaml --inference MODEL.OUT_PLANES 1 SYSTEM.NUM_CPUS 0 MODEL.IMAGE_MODEL_CKPT /braindat/lab/liusl/flywire/experiment/ckpts/embeddings/checkpoint_best_Unet2.pth INFERENCE.OUTPUT_PATH /braindat/lab/liusl/flywire/experiment/extract_pc_Intensity DATASET.INPUT_PATH /braindat/lab/liusl/flywire/block_data/v2/30_percent_test_3000 MODEL.IN_PLANES 4
#python main.py --config-base configs/Image-Base.yaml --config-file configs/Image-Unet-connector-extract_pc.yaml --inference SYSTEM.NUM_CPUS 0 MODEL.IMAGE_MODEL_CKPT /braindat/lab/liusl/flywire/experiment/ckpts/embeddings/checkpoint_best_Unet2.pth INFERENCE.OUTPUT_PATH /braindat/lab/liusl/flywire/experiment/extract_pc_Unet DATASET.INPUT_PATH /braindat/lab/liusl/flywire/block_data/v2/30_percent_test_3000 &
#sleep 60s
#python main.py --config-base configs/Image-Base.yaml --config-file configs/Image-Unet-connector-extract_pc.yaml --inference SYSTEM.NUM_CPUS 0 MODEL.IMAGE_MODEL_CKPT /braindat/lab/liusl/flywire/experiment/ckpts/embeddings/checkpoint_best_Unet2.pth INFERENCE.OUTPUT_PATH /braindat/lab/liusl/flywire/experiment/extract_pc_Unet DATASET.INPUT_PATH /braindat/lab/liusl/flywire/block_data/v2/30_percent_test_3000